"""Plano Premium (atividade 7): checkout do Stripe, webhook e status do plano.

Regra de ouro: `premium` só muda pelo webhook com assinatura validada. A success_url
do checkout não altera nada — ela só leva o usuário de volta para a SPA, que espera
o webhook chegar consultando /api/premium/status.
"""
import logging
from datetime import datetime
from typing import Optional

import stripe
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.clients import log_client
from app.clients.auth_client import forward_request
from app.core.api_responses import AUTH_SERVICE_INDISPONIVEL, STRIPE_NAO_CONFIGURADO, UNAUTHORIZED
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import current_user
from app.services import pagamentos

logger = logging.getLogger("nivelo.api.premium")

router = APIRouter(prefix="/api/premium", tags=["premium"])
webhook_router = APIRouter(tags=["premium"])

EVENTOS_TRATADOS = {"checkout.session.completed", "customer.subscription.deleted"}


class PremiumStatusOut(BaseModel):
    premium: bool
    premium_desde: Optional[datetime] = None


class CheckoutOut(BaseModel):
    url: str


def _exigir_stripe() -> None:
    if not settings.stripe_configurado:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pagamentos não configurados neste ambiente",
        )


@router.get("/status", response_model=PremiumStatusOut, responses={**UNAUTHORIZED, **AUTH_SERVICE_INDISPONIVEL})
async def status_premium(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    """Plano do usuário logado, lido do banco (não do JWT)."""
    usuario = await forward_request("GET", f"/users/{user['id']}")
    premium = bool(usuario.get("premium"))
    return PremiumStatusOut(
        premium=premium,
        premium_desde=usuario.get("premium_desde"),
    )


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    responses={
        **UNAUTHORIZED,
        409: {"description": "Usuário já é Premium", "content": {"application/json": {"example": {"detail": "Você já é Premium"}}}},
        502: {"description": "Stripe recusou ou não respondeu", "content": {"application/json": {"example": {"detail": "Não foi possível iniciar o pagamento"}}}},
        **STRIPE_NAO_CONFIGURADO,
    },
)
async def criar_checkout(request: Request, background: BackgroundTasks, user: dict = Depends(current_user)):
    """Cria a sessão de checkout e devolve a URL do Stripe; o Angular redireciona para ela."""
    _exigir_stripe()
    usuario = await forward_request("GET", f"/users/{user['id']}")
    if usuario.get("premium"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Você já é Premium")

    try:
        url = await run_in_threadpool(pagamentos.criar_sessao_checkout, user["id"], usuario.get("email", ""))
    except stripe.StripeError as exc:
        logger.warning("Stripe recusou o checkout do usuario_id=%s: %s", user["id"], type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Não foi possível iniciar o pagamento")

    background.add_task(log_client.registrar, "premium_checkout_iniciado", request, usuario_id=user["id"])
    return CheckoutOut(url=url)


def _recorte_do_evento(evento: dict) -> Optional[dict]:
    """Extrai só os IDs que o auth-service precisa. None = evento a ignorar."""
    tipo = evento.get("type")
    obj = (evento.get("data") or {}).get("object") or {}

    if tipo == "checkout.session.completed":
        if obj.get("mode") != "subscription" or obj.get("payment_status") not in ("paid", "no_payment_required"):
            return None
        ref = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("usuario_id")
        if not str(ref or "").isdigit():
            return None
        return {
            "usuario_id": int(ref),
            "customer_id": obj.get("customer"),
            "subscription_id": obj.get("subscription"),
        }

    if tipo == "customer.subscription.deleted":
        return {"subscription_id": obj.get("id")} if obj.get("id") else None

    return None


@webhook_router.post(
    "/webhooks/stripe",
    responses={
        400: {"description": "Assinatura ausente ou inválida", "content": {"application/json": {"example": {"detail": "Assinatura inválida"}}}},
        500: {"description": "Falha ao aplicar o evento (o Stripe reenvia)", "content": {"application/json": {"example": {"detail": "Falha ao processar o evento"}}}},
        **STRIPE_NAO_CONFIGURADO,
    },
)
async def stripe_webhook(request: Request, background: BackgroundTasks):
    """Recebe eventos do Stripe. Público (sem JWT), mas só aceita corpo assinado com STRIPE_WEBHOOK_SECRET."""
    _exigir_stripe()
    # Corpo BRUTO: a assinatura é calculada sobre os bytes exatos, não sobre o JSON reinterpretado
    payload = await request.body()
    assinatura = request.headers.get("stripe-signature")
    if not assinatura:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assinatura inválida")
    try:
        evento = pagamentos.validar_evento(payload, assinatura)
    except (ValueError, stripe.SignatureVerificationError):
        logger.warning("webhook do Stripe recusado: assinatura inválida")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assinatura inválida")

    event_id, tipo = evento.get("id"), evento.get("type")
    recorte = _recorte_do_evento(evento) if tipo in EVENTOS_TRATADOS else None
    if recorte is None:
        logger.info("webhook stripe %s %s ignorado", event_id, tipo)
        return {"ok": True}

    try:
        resultado = await forward_request(
            "POST",
            "/internal/premium/eventos",
            json_data={"event_id": event_id, "tipo": tipo, **recorte},
            interno=True,
        )
    except HTTPException as exc:
        # Qualquer falha vira 500: o Stripe reenvia, e a idempotência evita aplicar duas vezes
        logger.error("webhook stripe %s %s: auth-service respondeu %s", event_id, tipo, exc.status_code)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha ao processar o evento")

    usuario_id = resultado.get("usuario_id")
    logger.info(
        "webhook stripe %s %s usuario_id=%s duplicado=%s", event_id, tipo, usuario_id, resultado.get("duplicado")
    )
    if resultado.get("aplicado"):
        background.add_task(
            log_client.registrar,
            "premium_ativado" if resultado.get("premium") else "premium_cancelado",
            request,
            usuario_id=usuario_id,
            recurso=f"stripe:{event_id}",
            detalhes=tipo,
        )
    return {"ok": True}
