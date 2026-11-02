from sqlalchemy.orm import Session

from app.core.rbac_seed import LEGACY_ROLE_MAP, PAPEL_PADRAO
from app.core.security import hash_password
from app.models.papel import Papel
from app.models.permissao import Permissao
from app.models.usuario import Usuario
from app.models.usuario_permissao import UsuarioPermissao


def get_by_id(db: Session, user_id: int) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.id == user_id).first()


def get_by_email(db: Session, email: str) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.email == email.strip().lower()).first()


def list_all(db: Session) -> list[Usuario]:
    return db.query(Usuario).order_by(Usuario.id.asc()).all()


def create(db: Session, nome: str, email: str, senha: str, role: str = PAPEL_PADRAO) -> Usuario:
    raw_role = role.strip().lower() if role else PAPEL_PADRAO
    slug = LEGACY_ROLE_MAP.get(raw_role, raw_role)

    # Localiza o papel no banco
    papel = db.query(Papel).filter(Papel.slug == slug).first()
    if not papel:
        # Papel desconhecido: cai no de menor privilégio
        papel = db.query(Papel).filter(Papel.slug == PAPEL_PADRAO).first()
        slug = papel.slug if papel else PAPEL_PADRAO

    user = Usuario(
        nome=nome.strip(),
        email=email.strip().lower(),
        senha_hash=hash_password(senha),
        role=slug,
        role_id=papel.id if papel else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_role(db: Session, role_slug: str) -> Papel | None:
    slug = LEGACY_ROLE_MAP.get(role_slug.strip().lower(), role_slug.strip().lower())
    return db.query(Papel).filter(Papel.slug == slug).first()


def update_role(db: Session, user: Usuario, papel: Papel) -> Usuario:
    """Troca o plano do usuário. Os ajustes individuais de permissão são descartados."""
    user.role_id = papel.id
    user.role = papel.slug
    user.ajustes_permissao.clear()
    db.commit()
    db.refresh(user)
    return user


def set_permissions(db: Session, user: Usuario, permissoes: list[Permissao]) -> Usuario:
    """Define as permissões efetivas do usuário, gravando só a diferença em relação ao papel."""
    do_papel = {p.id for p in user.papel.permissoes} if user.papel else set()
    desejadas = {p.id for p in permissoes}

    user.ajustes_permissao.clear()
    db.flush()
    for perm_id in sorted(desejadas - do_papel):
        user.ajustes_permissao.append(UsuarioPermissao(permission_id=perm_id, concedida=True))
    for perm_id in sorted(do_papel - desejadas):
        user.ajustes_permissao.append(UsuarioPermissao(permission_id=perm_id, concedida=False))
    db.commit()
    db.refresh(user)
    return user


def delete(db: Session, user: Usuario) -> None:
    db.delete(user)
    db.commit()


def update_password(db: Session, user: Usuario, nova_senha: str) -> Usuario:
    user.senha_hash = hash_password(nova_senha)
    db.commit()
    db.refresh(user)
    return user
