"""Gauges da cobrança: lidos do banco a cada coleta, então valem com qualquer número de workers."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.metrics_core import Metric
from prometheus_client.registry import Collector
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.admin.application.metricas import resumir_cobranca
from app.admin.infrastructure.leituras import AssinaturasSQL

logger = logging.getLogger("nivelo.api.admin")


class ColetorDeAssinaturas(Collector):
    def __init__(self, abrir_sessao: Callable[[], Session]) -> None:
        self._abrir_sessao = abrir_sessao

    def collect(self) -> Iterable[Metric]:
        try:
            with self._abrir_sessao() as sessao:
                resumo = resumir_cobranca(AssinaturasSQL(sessao).linhas())
        except SQLAlchemyError:
            # O banco fora do ar não pode derrubar o /metrics inteiro
            logger.warning("não foi possível ler as assinaturas para o Prometheus", exc_info=True)
            return
        yield GaugeMetricFamily(
            "nivelo_mrr_centavos", "Soma mensal, em centavos, das assinaturas pagas ativas", value=resumo.mrr_centavos
        )
        yield GaugeMetricFamily(
            "nivelo_assinaturas_ativas", "Assinaturas pagas com status active", value=resumo.assinaturas_ativas
        )
