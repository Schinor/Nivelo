"""Vínculos do usuário, empresa nova e troca da empresa ativa (docs/adr/004).

Um token sem tenant (usuário sem vínculo) só serve aqui: listar vínculos e criar empresa.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_responses import UNAUTHORIZED
from app.core.database import get_db
from app.core.security import SessaoAtual, emitir_token, sessao_atual
from app.repositories import identidade_repo
from app.schemas.identidade import (
    ContextoOut,
    EmpresaAtivaIn,
    EmpresaCriadaOut,
    EmpresaIn,
    EmpresaOut,
    MembroDaEquipeOut,
    TokenOut,
    VinculoOut,
)
from app.schemas.usuario import UsuarioOut

router = APIRouter(tags=["identidade"])

DOCUMENTO_EM_USO = "Já existe uma empresa com este CPF/CNPJ"


def resposta_de_token(usuario, vinculo) -> dict:
    contexto = None
    if vinculo is not None:
        contexto = ContextoOut(empresa_id=vinculo.empresa_id, empresa_nome=vinculo.empresa.nome, papel=vinculo.papel)
    return {
        "access_token": emitir_token(usuario, vinculo),
        "token_type": "bearer",
        "user": UsuarioOut.model_validate(usuario),
        "contexto": contexto,
    }


@router.get("/vinculos", response_model=list[VinculoOut], responses={**UNAUTHORIZED})
def listar_vinculos(sessao: SessaoAtual = Depends(sessao_atual), db: Session = Depends(get_db)):
    """Empresas em que o usuário tem vínculo ativo, com o papel em cada uma."""
    return [
        VinculoOut(
            empresa_id=v.empresa_id,
            empresa_nome=v.empresa.nome,
            tipo_pessoa=v.empresa.tipo_pessoa,
            papel=v.papel,
            ativa=str(v.empresa_id) == sessao.empresa_id,
        )
        for v in identidade_repo.vinculos_ativos(db, sessao.usuario.id)
    ]


@router.post(
    "/empresas",
    response_model=EmpresaCriadaOut,
    status_code=status.HTTP_201_CREATED,
    responses={**UNAUTHORIZED, 403: {"description": "Admin da plataforma não cria empresa"}, 409: {}},
)
def criar_empresa(payload: EmpresaIn, sessao: SessaoAtual = Depends(sessao_atual), db: Session = Depends(get_db)):
    """Cria uma empresa com o usuário logado como `dono` e devolve um token com ela ativa."""
    usuario = sessao.usuario
    if usuario.admin_plataforma:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "O admin da plataforma não pertence a empresas")
    if payload.documento and identidade_repo.documento_em_uso(db, payload.documento):
        raise HTTPException(status.HTTP_409_CONFLICT, DOCUMENTO_EM_USO)
    try:
        vinculo = identidade_repo.criar_empresa_com_dono(
            db, usuario.id, payload.nome, payload.tipo_pessoa, payload.documento
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DOCUMENTO_EM_USO)
    return {**resposta_de_token(usuario, vinculo), "empresa": EmpresaOut.model_validate(vinculo.empresa)}


@router.post(
    "/empresa-ativa",
    response_model=TokenOut,
    responses={**UNAUTHORIZED, 403: {"description": "Vínculo desativado"}, 404: {"description": "Sem vínculo"}},
)
def trocar_empresa_ativa(
    payload: EmpresaAtivaIn, sessao: SessaoAtual = Depends(sessao_atual), db: Session = Depends(get_db)
):
    """Confere o vínculo com a empresa pedida e emite um token novo com ela ativa."""
    vinculo = identidade_repo.vinculo(db, sessao.usuario.id, uuid.UUID(str(payload.empresa_id)))
    if vinculo is None:
        # Não revela se a empresa existe
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada")
    if not vinculo.ativo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu vínculo com esta empresa foi desativado")
    return resposta_de_token(sessao.usuario, vinculo)


@router.get(
    "/equipe",
    response_model=list[MembroDaEquipeOut],
    responses={**UNAUTHORIZED, 403: {"description": "Só o dono da empresa ativa vê a equipe"}},
)
def listar_equipe(sessao: SessaoAtual = Depends(sessao_atual), db: Session = Depends(get_db)):
    """Pessoas com vínculo ativo na empresa ativa do token. Só o dono, conferido no banco."""
    if not sessao.empresa_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Escolha ou crie uma empresa para ver a equipe")
    empresa_id = uuid.UUID(sessao.empresa_id)
    meu = identidade_repo.vinculo(db, sessao.usuario.id, empresa_id)
    if meu is None or not meu.ativo or meu.papel != "dono":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o dono da empresa vê a equipe")
    return [
        MembroDaEquipeOut(usuario_id=u.id, nome=u.nome, email=u.email, papel=v.papel, desde=v.criado_em)
        for v, u in identidade_repo.equipe(db, empresa_id)
    ]
