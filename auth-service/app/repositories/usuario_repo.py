from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.usuario import Usuario


def get_by_id(db: Session, user_id: int) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.id == user_id).first()


def get_by_email(db: Session, email: str) -> Usuario | None:
    return db.query(Usuario).filter(Usuario.email == email.strip().lower()).first()


def list_all(db: Session) -> list[Usuario]:
    return db.query(Usuario).order_by(Usuario.id.asc()).all()


def create(db: Session, nome: str, email: str, senha: str) -> Usuario:
    """Usuário sem vínculo nem papel: o papel de negócio vem do vínculo com uma empresa."""
    user = Usuario(nome=nome.strip(), email=email.strip().lower(), senha_hash=hash_password(senha))
    db.add(user)
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
