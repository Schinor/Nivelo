"""Rotas internas do Plano Premium (atividade 7).

Quem fala com o Stripe é a API (único serviço exposto): ele valida a assinatura
do webhook e repassa aqui só os IDs do evento. Este serviço é o dono da tabela
`usuarios`, então é aqui que `premium` muda — junto com o registro do evento, na
mesma transação (idempotência).
"""
import hmac
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.repositories import premium_repo
from app.schemas.premium import PremiumEventoIn, PremiumEventoOut

logger = logging.getLogger("auth-service.premium")

router = APIRouter(prefix="/internal/premium", tags=["premium (interno)"])


def exigir_token_interno(x_internal_token: Optional[str] = Header(default=None)) -> None:
    if not settings.AUTH_INTERNAL_TOKEN:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rotas internas desabilitadas")
    if not x_internal_token or not hmac.compare_digest(x_internal_token, settings.AUTH_INTERNAL_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token interno inválido")


@router.post(
    "/eventos",
    response_model=PremiumEventoOut,
    dependencies=[Depends(exigir_token_interno)],
    responses={
        401: {"description": "Token interno ausente ou inválido", "content": {"application/json": {"example": {"detail": "Token interno inválido"}}}},
        503: {"description": "AUTH_INTERNAL_TOKEN não configurado", "content": {"application/json": {"example": {"detail": "Rotas internas desabilitadas"}}}},
    },
)
def processar_evento(payload: PremiumEventoIn, db: Session = Depends(get_db)):
    """Aplica um evento do Stripe já validado. Reenvio do mesmo `event_id` não altera nada."""
    if premium_repo.evento_ja_processado(db, payload.event_id):
        return PremiumEventoOut(duplicado=True, aplicado=False)

    usuario = None
    if payload.tipo == "checkout.session.completed" and payload.usuario_id is not None:
        usuario = premium_repo.ativar(db, payload.usuario_id, payload.customer_id, payload.subscription_id)
    elif payload.tipo == "customer.subscription.deleted" and payload.subscription_id:
        usuario = premium_repo.cancelar_por_assinatura(db, payload.subscription_id)

    premium_repo.registrar_evento(db, payload.event_id, payload.tipo)
    try:
        db.commit()
    except IntegrityError:
        # Duas entregas simultâneas do mesmo evento: a outra já gravou; esta é descartada inteira
        db.rollback()
        return PremiumEventoOut(duplicado=True, aplicado=False)

    if usuario is None:
        logger.warning("evento %s (%s) sem usuário correspondente", payload.event_id, payload.tipo)
        return PremiumEventoOut(duplicado=False, aplicado=False)

    logger.info("evento %s (%s): usuario_id=%s premium=%s", payload.event_id, payload.tipo, usuario.id, usuario.premium)
    return PremiumEventoOut(duplicado=False, aplicado=True, usuario_id=usuario.id, premium=usuario.premium)
