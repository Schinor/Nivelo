import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.assinaturas.application.assinatura_free import garantir_assinatura_free
from app.assinaturas.infrastructure.repositorio import RepositorioDeAssinaturasSQL
from app.clients import log_client
from app.clients.auth_client import forward_request
from app.core.api_responses import (
    AUTH_SERVICE_INDISPONIVEL,
    CREDENCIAIS_INVALIDAS,
    EMAIL_JA_CADASTRADO,
    NOT_FOUND_USER,
    RESET_TOKEN_INVALIDO,
    UNAUTHORIZED,
    forbidden,
    gestao_usuario_invalida,
)
from app.core.database import get_db
from app.dependencies import current_user, exigir_admin
from app.models.perfil import Perfil
from app.schemas.identidade import (
    CadastroIn,
    CadastroOut,
    EmpresaAtivaIn,
    EmpresaCriadaOut,
    EmpresaIn,
    MembroDaEquipeOut,
    TokenOut,
    VinculoOut,
)
from app.schemas.usuario import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UsuarioOut,
    ValidateTokenResponse,
)
from app.services import storage
from app.shared.api.autenticacao import requer_papel
from app.shared.application.contexto import TenantContext
from app.shared.domain.ids import EmpresaId

logger = logging.getLogger("nivelo.api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/cadastro",
    response_model=CadastroOut,
    status_code=status.HTTP_201_CREATED,
    responses={**EMAIL_JA_CADASTRADO, **AUTH_SERVICE_INDISPONIVEL},
)
async def cadastro(payload: CadastroIn, db: Session = Depends(get_db)):
    """Cria a empresa, o usuário e o vínculo `dono`. O papel nunca vem do corpo.

    A empresa nasce no plano Free: o módulo de assinaturas grava a própria tabela logo depois
    (o auth-service não escreve em tabela de outro contexto).
    """
    resposta = await forward_request("POST", "/cadastro", json_data=payload.model_dump(mode="json"))
    _assinatura_free(db, resposta.get("empresa", {}).get("id"))
    return resposta


def _assinatura_free(db: Session, empresa_id: str | None) -> None:
    """Falha aqui não desfaz o cadastro: a Fase 8 também cria a assinatura Free sob demanda."""
    if not empresa_id:
        return
    try:
        garantir_assinatura_free(RepositorioDeAssinaturasSQL(db), EmpresaId.de_texto(empresa_id))
    except Exception:
        logger.exception("não foi possível criar a assinatura Free da empresa %s", empresa_id)


def _repassar_token(request: Request) -> dict[str, str]:
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não enviado", headers={"WWW-Authenticate": "Bearer"}
        )
    return {"authorization": auth_header}


@router.get("/vinculos", response_model=list[VinculoOut], responses={**UNAUTHORIZED, **AUTH_SERVICE_INDISPONIVEL})
async def listar_vinculos(request: Request):
    """Empresas do usuário e o papel em cada uma. Funciona com token sem tenant."""
    return await forward_request("GET", "/vinculos", headers=_repassar_token(request))


@router.get(
    "/equipe",
    response_model=list[MembroDaEquipeOut],
    responses={**UNAUTHORIZED, 403: {"description": "Só o dono"}, **AUTH_SERVICE_INDISPONIVEL},
)
async def listar_equipe(request: Request, _ctx: TenantContext = Depends(requer_papel("dono"))):
    """Quem tem vínculo ativo na empresa ativa (para escolher membros das obras). Só o dono."""
    return await forward_request("GET", "/equipe", headers=_repassar_token(request))


@router.post(
    "/empresas",
    response_model=EmpresaCriadaOut,
    status_code=status.HTTP_201_CREATED,
    responses={**UNAUTHORIZED, **AUTH_SERVICE_INDISPONIVEL},
)
async def criar_empresa(payload: EmpresaIn, request: Request, db: Session = Depends(get_db)):
    """Nova empresa com o usuário logado como dono. Funciona com token sem tenant. Nasce no Free."""
    resposta = await forward_request(
        "POST", "/empresas", json_data=payload.model_dump(mode="json"), headers=_repassar_token(request)
    )
    _assinatura_free(db, resposta.get("empresa", {}).get("id"))
    return resposta


@router.post("/empresa-ativa", response_model=TokenOut, responses={**UNAUTHORIZED, **AUTH_SERVICE_INDISPONIVEL})
async def trocar_empresa_ativa(payload: EmpresaAtivaIn, request: Request):
    """Troca a empresa ativa: confere o vínculo e devolve um token novo."""
    return await forward_request(
        "POST", "/empresa-ativa", json_data=payload.model_dump(mode="json"), headers=_repassar_token(request)
    )


@router.post(
    "/login",
    response_model=TokenOut,
    responses={**CREDENCIAIS_INVALIDAS, **AUTH_SERVICE_INDISPONIVEL},
)
async def login(
    request: Request,
    background: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    try:
        resposta = await forward_request(
            "POST",
            "/login",
            data={"username": form_data.username, "password": form_data.password},
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            # Await direto: BackgroundTasks se perde quando a rota levanta exceção
            await log_client.registrar(
                "login_falhou",
                request,
                detalhes=f"email:{form_data.username[:150]}",
            )
        raise

    background.add_task(
        log_client.registrar,
        "login",
        request,
        usuario_id=(resposta.get("user") or {}).get("id"),
    )
    return resposta


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**UNAUTHORIZED},
)
async def logout(
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(current_user),
):
    """Registra o logout na trilha de auditoria. O JWT é stateless, então nada é invalidado."""
    background.add_task(log_client.registrar, "logout", request, usuario_id=user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UsuarioOut, responses={**UNAUTHORIZED, **AUTH_SERVICE_INDISPONIVEL})
async def me(request: Request):
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não fornecido")
    return await forward_request(
        "GET",
        "/me",
        headers={"authorization": auth_header},
    )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    responses={**AUTH_SERVICE_INDISPONIVEL},
)
async def forgot_password(payload: ForgotPasswordRequest):
    return await forward_request("POST", "/forgot-password", json_data=payload.model_dump())


@router.get(
    "/validate-reset-token/{token}",
    response_model=ValidateTokenResponse,
    responses={**AUTH_SERVICE_INDISPONIVEL},
)
async def validate_reset_token(token: str):
    return await forward_request("GET", f"/validate-reset-token/{token}")


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={**RESET_TOKEN_INVALIDO, **AUTH_SERVICE_INDISPONIVEL},
)
async def reset_password(payload: ResetPasswordRequest):
    return await forward_request("POST", "/reset-password", json_data=payload.model_dump())


@router.get(
    "/users",
    response_model=list[UsuarioOut],
    responses={**UNAUTHORIZED, **forbidden("admin da plataforma"), **AUTH_SERVICE_INDISPONIVEL},
)
async def list_users(request: Request, _admin: dict = Depends(exigir_admin)):
    return await forward_request("GET", "/users", headers={"authorization": request.headers.get("authorization")})


def _apagar_foto_best_effort(chave: str) -> None:
    try:
        storage.apagar_objeto(chave)
    except Exception:
        logger.warning("não foi possível apagar a foto %s do usuário removido", chave)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **gestao_usuario_invalida(),
        **UNAUTHORIZED,
        **forbidden("admin da plataforma"),
        **NOT_FOUND_USER,
        **AUTH_SERVICE_INDISPONIVEL,
    },
)
async def delete_user(
    user_id: int,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: dict = Depends(exigir_admin),
):
    """Remove o perfil (com a foto) na API e, em seguida, a conta no auth-service.

    As recusas do auth-service (própria conta, usuário inexistente) são conferidas
    antes de apagar qualquer coisa.
    """
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar ou remover a sua própria conta por aqui",
        )
    await forward_request("GET", f"/users/{user_id}", interno=True)  # 404 se não existir

    perfil = db.get(Perfil, user_id)
    foto_key = perfil.foto_key if perfil else None
    if perfil:
        db.delete(perfil)
    db.commit()

    await forward_request(
        "DELETE",
        f"/users/{user_id}",
        headers={"authorization": request.headers.get("authorization")},
    )

    if foto_key:
        background.add_task(_apagar_foto_best_effort, foto_key)

    background.add_task(
        log_client.registrar,
        "usuario_removido",
        request,
        usuario_id=admin["id"],
        recurso=f"usuario:{user_id}",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/status",
    responses={**UNAUTHORIZED, **forbidden("admin da plataforma"), **AUTH_SERVICE_INDISPONIVEL},
)
async def admin_status(request: Request, _admin: dict = Depends(exigir_admin)):
    return await forward_request(
        "GET", "/admin/status", headers={"authorization": request.headers.get("authorization")}
    )
