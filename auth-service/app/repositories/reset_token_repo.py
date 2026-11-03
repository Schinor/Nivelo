"""Pedidos de redefinição de senha. O token em claro só existe na memória e no e-mail; o
banco guarda o SHA-256 dele, como nos convites."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_de_token
from app.models.reset_token import ResetToken


def create_reset_token(db: Session, usuario_id: int) -> tuple[ResetToken, str]:
    """Grava o pedido e devolve (registro, token em claro). O token em claro vai só no e-mail."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    reset_token = ResetToken(
        token_hash=hash_de_token(token),
        usuario_id=usuario_id,
        criado_em=now,
        expira_em=now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        usado=False,
    )
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return reset_token, token


def count_recent(db: Session, usuario_id: int, window_minutes: int) -> int:
    # criado_em é gravado como UTC sem fuso no banco
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=window_minutes)
    return db.query(ResetToken).filter(ResetToken.usuario_id == usuario_id, ResetToken.criado_em >= since).count()


def get_by_token(db: Session, token: str) -> ResetToken | None:
    return db.query(ResetToken).filter(ResetToken.token_hash == hash_de_token(token)).first()


def consumir(db: Session, reset_token: ResetToken) -> bool:
    """Marca o token como usado com um UPDATE condicional, sem commit. Devolve False se outro
    pedido já o usou (dois envios do mesmo link ao mesmo tempo: só um passa)."""
    marcado = db.execute(
        update(ResetToken)
        .where(ResetToken.id == reset_token.id, ResetToken.usado.is_(False))
        .values(usado=True)
        .execution_options(synchronize_session=False)
    )
    return marcado.rowcount == 1
