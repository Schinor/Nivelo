"""Admin da plataforma criado por variável de ambiente, nunca pelo cadastro público."""

import logging

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.usuario import Usuario

logger = logging.getLogger("auth-service.admin")

SENHA_MINIMA = 12


def garantir_admin(db: Session, email: str, senha_inicial: str) -> Usuario | None:
    """Cria o admin no primeiro boot; se o e-mail já existir, só garante a marca de admin.

    A senha só é usada na criação: reiniciar o serviço nunca troca a senha de quem já existe.
    Sem as duas variáveis, não faz nada.
    """
    email = (email or "").strip().lower()
    if not email or not senha_inicial:
        return None
    if len(senha_inicial) < SENHA_MINIMA:
        raise ValueError(f"ADMIN_SENHA_INICIAL precisa de pelo menos {SENHA_MINIMA} caracteres")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        usuario = Usuario(
            nome="Admin da plataforma",
            email=email,
            senha_hash=hash_password(senha_inicial),
            role="admin",  # legado, sai com a coluna antiga (ADR 009)
            admin_plataforma=True,
        )
        db.add(usuario)
        logger.warning("Admin da plataforma criado: %s", email)
    elif not usuario.admin_plataforma:
        usuario.admin_plataforma = True
        logger.warning("Usuário existente promovido a admin da plataforma: %s", email)
    db.commit()
    return usuario
