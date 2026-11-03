"""Gestão de contas pela plataforma. Só o admin da plataforma (ou a API, pelo token interno)."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.api_responses import NOT_FOUND_USER, UNAUTHORIZED, gestao_usuario_invalida
from app.core.config import settings
from app.core.database import get_db
from app.core.security import exigir_admin, get_current_user, oauth2_scheme
from app.models.usuario import Usuario
from app.repositories import usuario_repo
from app.schemas.usuario import UsuarioOut

router = APIRouter(prefix="", tags=["contas (admin)"])

SO_ADMIN = {403: {"description": "Acesso restrito ao admin da plataforma"}}


@router.get("/users", response_model=list[UsuarioOut], responses={**UNAUTHORIZED, **SO_ADMIN})
def list_users(db: Session = Depends(get_db), _admin=Depends(exigir_admin)):
    return usuario_repo.list_all(db)


def _usuario_gerenciavel(db: Session, user_id: int, admin) -> Usuario:
    """Busca o alvo de uma ação administrativa; o admin não pode agir sobre a própria conta."""
    usuario = usuario_repo.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if usuario.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar ou remover a sua própria conta por aqui",
        )
    return usuario


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**gestao_usuario_invalida(), **UNAUTHORIZED, **SO_ADMIN, **NOT_FOUND_USER},
)
def delete_user(user_id: int, db: Session = Depends(get_db), admin=Depends(exigir_admin)):
    usuario = _usuario_gerenciavel(db, user_id, admin)
    usuario_repo.delete(db, usuario)


def _admin_ou_interno(
    x_internal_token: str | None = Header(default=None),
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> None:
    """A API consulta contas pelo token interno; fora isso, só o admin."""
    if settings.AUTH_INTERNAL_TOKEN and x_internal_token:
        if hmac.compare_digest(x_internal_token, settings.AUTH_INTERNAL_TOKEN):
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token interno inválido")
    exigir_admin(get_current_user(token, db))


@router.get(
    "/users/{user_id}",
    response_model=UsuarioOut,
    dependencies=[Depends(_admin_ou_interno)],
    responses={**UNAUTHORIZED, **SO_ADMIN, **NOT_FOUND_USER},
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    usuario = usuario_repo.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return usuario


@router.get("/admin/status", responses={**UNAUTHORIZED, **SO_ADMIN})
def admin_status(_admin=Depends(exigir_admin)):
    return {
        "status": "online",
        "admin_access": True,
        "message": "Painel de controle administrativo autorizado.",
    }
