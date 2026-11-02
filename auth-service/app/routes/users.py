from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.api_responses import NOT_FOUND_USER, UNAUTHORIZED, forbidden, gestao_usuario_invalida
from app.core.database import get_db
from app.core.security import require_permission
from app.models.papel import Papel
from app.models.permissao import Permissao
from app.models.usuario import Usuario
from app.repositories import usuario_repo
from app.schemas.usuario import (
    PapelCreate,
    PapelOut,
    PermissaoOut,
    UserPermissionsUpdate,
    UserRoleOut,
    UserRoleUpdate,
    UsuarioOut,
)

router = APIRouter(prefix="", tags=["users & rbac"])


@router.get(
    "/users",
    response_model=list[UsuarioOut],
    responses={**UNAUTHORIZED, **forbidden("gerenciar:usuarios")},
)
def list_users(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("gerenciar:usuarios")),
):
    return usuario_repo.list_all(db)


@router.get("/users/{user_id}/role", response_model=UserRoleOut, responses={**NOT_FOUND_USER})
def get_user_role(user_id: int, db: Session = Depends(get_db)):
    usuario = usuario_repo.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return {
        "user_id": usuario.id,
        "role": usuario.role,
        "role_id": usuario.role_id,
        "permissions": usuario.permissions,
    }


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


@router.put(
    "/users/{user_id}/role",
    response_model=UsuarioOut,
    responses={
        **gestao_usuario_invalida(plano_inexistente="Plano inexistente"),
        **UNAUTHORIZED,
        **forbidden("gerenciar:usuarios"),
        **NOT_FOUND_USER,
    },
)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_permission("gerenciar:usuarios")),
):
    usuario = _usuario_gerenciavel(db, user_id, admin)
    papel = usuario_repo.get_role(db, payload.role)
    if not papel:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plano inexistente")
    return usuario_repo.update_role(db, usuario, papel)


@router.put(
    "/users/{user_id}/permissions",
    response_model=UsuarioOut,
    responses={
        **gestao_usuario_invalida(permissao_inexistente="Permissões inexistentes: voar:nave"),
        **UNAUTHORIZED,
        **forbidden("gerenciar:usuarios"),
        **NOT_FOUND_USER,
    },
)
def update_user_permissions(
    user_id: int,
    payload: UserPermissionsUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_permission("gerenciar:usuarios")),
):
    usuario = _usuario_gerenciavel(db, user_id, admin)
    por_slug = {p.slug: p for p in db.query(Permissao).all()}
    desconhecidas = sorted(set(payload.permissions) - por_slug.keys())
    if desconhecidas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Permissões inexistentes: {', '.join(desconhecidas)}",
        )
    permissoes = [por_slug[s] for s in set(payload.permissions)]
    return usuario_repo.set_permissions(db, usuario, permissoes)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **gestao_usuario_invalida(),
        **UNAUTHORIZED,
        **forbidden("gerenciar:usuarios"),
        **NOT_FOUND_USER,
    },
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_permission("gerenciar:usuarios")),
):
    usuario = _usuario_gerenciavel(db, user_id, admin)
    usuario_repo.delete(db, usuario)


@router.get("/users/{user_id}", response_model=UsuarioOut, responses={**NOT_FOUND_USER})
def get_user(user_id: int, db: Session = Depends(get_db)):
    usuario = usuario_repo.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return usuario


@router.get("/roles", response_model=list[PapelOut])
def list_roles(db: Session = Depends(get_db)):
    return db.query(Papel).all()


@router.post(
    "/roles",
    response_model=PapelOut,
    status_code=status.HTTP_201_CREATED,
    responses={**UNAUTHORIZED, **forbidden("gerenciar:papeis")},
)
def create_or_update_role(
    payload: PapelCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("gerenciar:papeis")),
):
    role = db.query(Papel).filter(Papel.slug == payload.slug).first()
    if not role:
        role = Papel(name=payload.name, slug=payload.slug, description=payload.description)
        db.add(role)
    else:
        role.name = payload.name
        role.description = payload.description

    if payload.permission_ids:
        perms = db.query(Permissao).filter(Permissao.id.in_(payload.permission_ids)).all()
        role.permissoes = perms

    db.commit()
    db.refresh(role)
    return role


@router.get(
    "/permissions",
    response_model=list[PermissaoOut],
    responses={**UNAUTHORIZED, **forbidden("gerenciar:permissoes")},
)
def list_permissions(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("gerenciar:permissoes")),
):
    return db.query(Permissao).all()


@router.get(
    "/admin/status",
    responses={**UNAUTHORIZED, **forbidden("administrar:sistema")},
)
def admin_status(
    _user=Depends(require_permission("administrar:sistema")),
):
    return {
        "status": "online",
        "admin_access": True,
        "message": "Painel de controle administrativo autorizado.",
    }
