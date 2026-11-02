import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.reset_token import ResetToken


def create_reset_token(db: Session, usuario_id: int) -> ResetToken:
    token_str = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expira_em = now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)

    reset_token = ResetToken(
        token=token_str,
        usuario_id=usuario_id,
        criado_em=now,
        expira_em=expira_em,
        usado=False,
    )
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return reset_token


def count_recent(db: Session, usuario_id: int, window_minutes: int) -> int:
    # criado_em é gravado como UTC sem fuso no banco
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=window_minutes)
    return db.query(ResetToken).filter(ResetToken.usuario_id == usuario_id, ResetToken.criado_em >= since).count()


def get_by_token(db: Session, token: str) -> ResetToken | None:
    return db.query(ResetToken).filter(ResetToken.token == token.strip()).first()


def mark_as_used(db: Session, reset_token: ResetToken) -> None:
    reset_token.usado = True
    db.commit()
