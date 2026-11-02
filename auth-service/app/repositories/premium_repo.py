from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.stripe_evento import StripeEventoProcessado
from app.models.usuario import Usuario


def evento_ja_processado(db: Session, event_id: str) -> bool:
    return db.get(StripeEventoProcessado, event_id) is not None


def registrar_evento(db: Session, event_id: str, tipo: str) -> None:
    """Só adiciona na sessão: o commit é do chamador, junto com a mudança no usuário."""
    db.add(StripeEventoProcessado(event_id=event_id, tipo=tipo))


def ativar(db: Session, usuario_id: int, customer_id: str | None, subscription_id: str | None) -> Usuario | None:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        return None
    usuario.premium = True
    usuario.stripe_customer_id = customer_id or usuario.stripe_customer_id
    usuario.stripe_subscription_id = subscription_id
    usuario.premium_desde = datetime.now(UTC)
    return usuario


def cancelar_por_assinatura(db: Session, subscription_id: str) -> Usuario | None:
    """Assinatura antiga (o usuário já assinou de novo) não casa com nenhum usuário: nada muda."""
    usuario = db.query(Usuario).filter(Usuario.stripe_subscription_id == subscription_id).first()
    if usuario is None:
        return None
    usuario.premium = False
    usuario.stripe_subscription_id = None
    usuario.premium_desde = None
    return usuario
