"""Dependências das rotas de Assinaturas."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.assinaturas.application.portas import GatewayDePagamentos
from app.assinaturas.domain.assinatura import PrecosDosPlanos
from app.assinaturas.infrastructure.stripe_gateway import StripeGateway
from app.core.config import settings


def gateway_de_pagamentos() -> GatewayDePagamentos:
    if not settings.stripe_configurado:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Pagamentos não configurados neste ambiente")
    return StripeGateway(settings.STRIPE_SECRET_KEY, settings.STRIPE_WEBHOOK_SECRET, settings.FRONTEND_URL)


def precos_dos_planos() -> PrecosDosPlanos:
    return PrecosDosPlanos(pro=settings.STRIPE_PRICE_PRO, construtora=settings.STRIPE_PRICE_CONSTRUTORA)
