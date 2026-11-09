"""Processa um aviso do meio de pagamento: idempotente e sempre a partir da fonte da verdade.

O conteúdo do aviso só diz qual assinatura olhar; o estado vem de `buscar_assinatura`. Assim,
avisos repetidos ou fora de ordem gravam o mesmo resultado.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.assinaturas.application.portas import GatewayDePagamentos, LivroDoWebhook
from app.assinaturas.domain.assinatura import (
    EVENTOS_TRATADOS,
    AssinaturaNoPagamento,
    EventoDePagamento,
    PrecosDosPlanos,
    evento_da_mudanca,
)
from app.assinaturas.domain.eventos import AssinaturaInadimplente
from app.shared.domain.ids import EmpresaId

logger = logging.getLogger("nivelo.api.assinaturas")


@dataclass(frozen=True, slots=True)
class ResultadoDoAviso:
    situacao: str  # aplicado | duplicado | ignorado
    avisar_inadimplencia: EmpresaId | None = None


IGNORADO = ResultadoDoAviso("ignorado")
DUPLICADO = ResultadoDoAviso("duplicado")


def processar_aviso(
    aviso: EventoDePagamento, gateway: GatewayDePagamentos, livro: LivroDoWebhook, precos: PrecosDosPlanos
) -> ResultadoDoAviso:
    if aviso.tipo not in EVENTOS_TRATADOS:
        return IGNORADO
    if not livro.registrar_recebimento(aviso.id, aviso.tipo):
        return DUPLICADO
    try:
        externa = gateway.buscar_assinatura(aviso.subscription_id) if aviso.subscription_id else None
        return _aplicar(aviso, externa, livro, precos)
    except Exception as erro:
        livro.rollback()
        livro.registrar_erro(aviso.id, type(erro).__name__)
        raise


def _aplicar(
    aviso: EventoDePagamento, externa: AssinaturaNoPagamento | None, livro: LivroDoWebhook, precos: PrecosDosPlanos
) -> ResultadoDoAviso:
    empresa = None
    if externa is not None:
        empresa = (
            externa.empresa_id
            or aviso.empresa_id
            or livro.empresa_da_assinatura(externa.subscription_id, externa.customer_id)
        )
    # A marca entra na mesma transação da mudança: só uma entrega simultânea segue adiante
    if not livro.marcar_processado(aviso.id):
        livro.rollback()
        return DUPLICADO
    if externa is None or empresa is None:
        logger.warning("aviso %s (%s) sem assinatura ou empresa conhecida: ignorado", aviso.id, aviso.tipo)
        livro.commit()
        return IGNORADO

    atual = livro.travar(empresa)
    if atual.e_assinatura_antiga(externa):
        logger.info("aviso %s da assinatura antiga %s: ignorado", aviso.id, externa.subscription_id)
        livro.commit()
        return IGNORADO

    nova = atual.sincronizada_com(externa, precos)
    if nova != atual:
        livro.salvar(nova)
    evento = evento_da_mudanca(atual, nova, aviso.tipo, externa.usuario_id) if externa.usuario_id else None
    if evento is not None:
        livro.publicar([evento])
    livro.commit()
    avisar = empresa if isinstance(evento, AssinaturaInadimplente) else None
    return ResultadoDoAviso("aplicado", avisar_inadimplencia=avisar)
