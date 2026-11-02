"""Integração com o Stripe (Plano Premium, sempre em modo de teste).

O cartão é digitado SÓ na página hospedada do Stripe (Checkout): nenhum dado de
cartão passa pela API. Daqui saem e chegam apenas IDs (cus_..., sub_..., evt_...).
"""
import json

import stripe

from app.core.config import settings


def criar_sessao_checkout(usuario_id: int, email: str) -> str:
    """Cria a Checkout Session da assinatura mensal e devolve a URL hospedada do Stripe."""
    base = settings.FRONTEND_URL.rstrip("/")
    sessao = stripe.checkout.Session.create(
        api_key=settings.STRIPE_SECRET_KEY,
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        # Ligação pagamento ↔ usuário: volta no evento checkout.session.completed
        client_reference_id=str(usuario_id),
        metadata={"usuario_id": str(usuario_id)},
        customer_email=email or None,
        success_url=f"{base}/premium/sucesso?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/premium/cancelado",
    )
    return sessao.url


def validar_evento(payload: bytes, assinatura: str) -> dict:
    """Confere a assinatura sobre o CORPO BRUTO e devolve o evento como dict.

    Levanta ValueError (payload inválido) ou stripe.SignatureVerificationError.
    """
    stripe.Webhook.construct_event(payload, assinatura, settings.STRIPE_WEBHOOK_SECRET)
    # Assinatura ok: o JSON é lido dos mesmos bytes que foram assinados
    return json.loads(payload)
