from typing import Literal, Optional
from pydantic import BaseModel


class PremiumEventoIn(BaseModel):
    """Recorte de um evento do Stripe cuja assinatura JÁ foi validada pela API.

    Só IDs: o payload completo do Stripe não trafega nem é gravado.
    """

    event_id: str
    tipo: Literal["checkout.session.completed", "customer.subscription.deleted"]
    usuario_id: Optional[int] = None
    customer_id: Optional[str] = None
    subscription_id: Optional[str] = None


class PremiumEventoOut(BaseModel):
    # True = o event_id já tinha sido processado; nada foi alterado
    duplicado: bool
    # True = algum usuário mudou de plano por causa deste evento
    aplicado: bool
    usuario_id: Optional[int] = None
    premium: Optional[bool] = None
