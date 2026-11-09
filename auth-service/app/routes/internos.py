"""Rotas chamadas só pela API, pela rede interna, com o token compartilhado."""

import hmac
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.email import send_aviso_de_inadimplencia_email
from app.repositories import identidade_repo

logger = logging.getLogger("auth-service.internos")


def exigir_token_interno(x_internal_token: str | None = Header(default=None)) -> None:
    if not settings.AUTH_INTERNAL_TOKEN:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rotas internas desabilitadas")
    if not x_internal_token or not hmac.compare_digest(x_internal_token, settings.AUTH_INTERNAL_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token interno inválido")


router = APIRouter(prefix="/internal", tags=["interno"], dependencies=[Depends(exigir_token_interno)])


class AvisoDeInadimplenciaIn(BaseModel):
    empresa_id: uuid.UUID


class AvisoDeInadimplenciaOut(BaseModel):
    enviados: int


class EmpresaDaPlataformaOut(BaseModel):
    id: uuid.UUID
    nome: str
    usuario_ids: list[int]


class UsuarioDaPlataformaOut(BaseModel):
    id: int
    nome: str
    admin: bool


class ContasDaPlataformaOut(BaseModel):
    empresas: list[EmpresaDaPlataformaOut]
    usuarios: list[UsuarioDaPlataformaOut]


@router.post("/avisos/inadimplencia", response_model=AvisoDeInadimplenciaOut)
def avisar_inadimplencia(payload: AvisoDeInadimplenciaIn, db: Session = Depends(get_db)):
    """Avisa os donos da empresa de que o pagamento da assinatura falhou."""
    enviados = 0
    for vinculo, usuario in identidade_repo.equipe(db, payload.empresa_id):
        if vinculo.papel != "dono":
            continue
        try:
            send_aviso_de_inadimplencia_email(usuario.email, vinculo.empresa.nome)
            enviados += 1
        except Exception:
            logger.exception("aviso de inadimplência não enviado ao usuario_id=%s", usuario.id)
    return AvisoDeInadimplenciaOut(enviados=enviados)


@router.get("/metricas/contas", response_model=ContasDaPlataformaOut)
def contas_da_plataforma(db: Session = Depends(get_db)):
    """Empresas com seus vínculos ativos e as contas, para o painel do admin. Sem e-mails."""
    empresas, usuarios = identidade_repo.contas_da_plataforma(db)
    return ContasDaPlataformaOut(
        empresas=[EmpresaDaPlataformaOut(id=e.id, nome=e.nome, usuario_ids=ids) for e, ids in empresas],
        usuarios=[UsuarioDaPlataformaOut(id=u.id, nome=u.nome, admin=u.admin) for u in usuarios],
    )
