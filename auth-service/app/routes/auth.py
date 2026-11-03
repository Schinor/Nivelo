import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_responses import (
    CREDENCIAIS_INVALIDAS,
    RESET_TOKEN_INVALIDO,
    UNAUTHORIZED,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.email import send_password_reset_email
from app.core.security import get_current_user, hash_password, verify_password
from app.models.usuario import Usuario
from app.repositories import identidade_repo, reset_token_repo, usuario_repo
from app.routes.identidade import DOCUMENTO_EM_USO, resposta_de_token
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ValidateTokenResponse,
)
from app.schemas.identidade import CadastroIn, CadastroOut, TokenOut
from app.schemas.usuario import UsuarioOut

logger = logging.getLogger("auth-service.auth")

router = APIRouter(tags=["auth"])

FORGOT_PASSWORD_MESSAGE = (
    "Se o e-mail informado estiver cadastrado, enviaremos um link para redefinir a senha. "
    "Verifique sua caixa de entrada e o spam."
)


EMAIL_EM_USO = 'Este e-mail já tem conta. Entre com ele e crie a nova empresa em "Nova empresa" (POST /auth/empresas).'


@router.post(
    "/cadastro",
    response_model=CadastroOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "E-mail ou CPF/CNPJ já cadastrado"}},
)
def cadastro(payload: CadastroIn, db: Session = Depends(get_db)):
    """Cria a empresa, o usuário e o vínculo `dono` numa transação só.

    O papel nunca vem do corpo: quem se cadastra é sempre o dono da empresa que está criando.
    """
    if usuario_repo.get_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_EM_USO)
    if payload.documento and identidade_repo.documento_em_uso(db, payload.documento):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DOCUMENTO_EM_USO)

    usuario = Usuario(
        nome=payload.nome,
        email=payload.email.strip().lower(),
        senha_hash=hash_password(payload.senha),
    )
    try:
        db.add(usuario)
        db.flush()
        vinculo = identidade_repo.criar_empresa_com_dono(
            db, usuario.id, payload.empresa_nome, payload.tipo_pessoa, payload.documento
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail ou CPF/CNPJ já cadastrado")
    db.refresh(usuario)
    return {"usuario": usuario, "empresa": vinculo.empresa, "papel": vinculo.papel}


@router.post("/login", response_model=TokenOut, responses={**CREDENCIAIS_INVALIDAS})
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Escolhe o vínculo ativo mais recente. Sem vínculo, o token sai sem tenant."""
    usuario = usuario_repo.get_by_email(db, form_data.username)
    if not usuario or not verify_password(form_data.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    vinculo = None if usuario.admin_plataforma else identidade_repo.vinculo_para_login(db, usuario.id)
    return resposta_de_token(usuario, vinculo)


@router.get("/me", response_model=UsuarioOut, responses={**UNAUTHORIZED})
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # Resposta sempre neutra: não revela se o e-mail está cadastrado nem se o envio falhou
    usuario = usuario_repo.get_by_email(db, payload.email)
    if not usuario:
        return {"message": FORGOT_PASSWORD_MESSAGE}

    recentes = reset_token_repo.count_recent(db, usuario.id, settings.RESET_REQUEST_WINDOW_MINUTES)
    if recentes >= settings.RESET_REQUEST_LIMIT:
        logger.warning("Limite de solicitações de redefinição atingido para o usuário id=%s", usuario.id)
        return {"message": FORGOT_PASSWORD_MESSAGE}

    reset_token = reset_token_repo.create_reset_token(db, usuario.id)

    try:
        send_password_reset_email(
            to_email=usuario.email,
            token=reset_token.token,
            user_name=usuario.nome,
        )
    except Exception:
        # Já registrado em send_password_reset_email; mantém a resposta neutra
        pass

    return {"message": FORGOT_PASSWORD_MESSAGE}


@router.get("/validate-reset-token/{token}", response_model=ValidateTokenResponse)
def validate_reset_token(token: str, db: Session = Depends(get_db)):
    reset_token = reset_token_repo.get_by_token(db, token)
    if not reset_token:
        return {"valid": False, "message": "Token de recuperação inválido ou não encontrado."}

    now_utc = datetime.now(UTC)
    expira_em = reset_token.expira_em
    if expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=UTC)

    if now_utc >= expira_em:
        return {"valid": False, "message": "Link de recuperação expirado (limite de 30 minutos excedido)."}

    if reset_token.usado:
        return {"valid": False, "message": "Este link de recuperação já foi utilizado."}

    usuario = usuario_repo.get_by_id(db, reset_token.usuario_id)
    return {
        "valid": True,
        "email": usuario.email if usuario else None,
        "message": "Token válido.",
    }


@router.post("/reset-password", response_model=ResetPasswordResponse, responses={**RESET_TOKEN_INVALIDO})
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset_token = reset_token_repo.get_by_token(db, payload.token)
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperação inválido ou inexistente.",
        )

    now_utc = datetime.now(UTC)
    expira_em = reset_token.expira_em
    if expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=UTC)

    if now_utc >= expira_em:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O link de recuperação expirou (validade de 30 minutos). Solicite uma nova recuperação.",
        )

    if reset_token.usado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link de recuperação já foi utilizado anteriormente.",
        )

    if len(payload.nova_senha) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ter no mínimo 6 caracteres.",
        )

    usuario = usuario_repo.get_by_id(db, reset_token.usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário associado ao token não encontrado.",
        )

    usuario_repo.update_password(db, usuario, payload.nova_senha)
    reset_token_repo.mark_as_used(db, reset_token)

    return {"message": "Senha redefinida com sucesso! Você já pode fazer login com a nova senha."}
