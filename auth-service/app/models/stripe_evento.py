from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StripeEventoProcessado(Base):
    """Idempotência do webhook: o Stripe pode reenviar o mesmo evento várias vezes.

    O id do evento é gravado na MESMA transação que altera o usuário, então ou os dois
    ficam gravados ou nenhum — um reenvio nunca aplica a mudança duas vezes.
    """

    __tablename__ = "stripe_eventos_processados"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    processado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
