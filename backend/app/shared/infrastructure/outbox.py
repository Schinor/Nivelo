"""Outbox transacional dos eventos de negócio e o relay que os publica (ADR 003 e 012).

1. A unidade de trabalho chama `gravar_na_outbox` antes do commit: o agregado e os eventos
   dele entram na mesma transação. Se o dado foi gravado, o evento também foi.
2. O `RelayDaOutbox` lê até `lote` linhas pendentes e prontas, publica o lote de uma vez e
   marca `publicado_em`. A entrega é "pelo menos uma vez"; o log-service ignora `event_id`
   repetido.
3. Falha com backoff exponencial por linha: cada falha soma `tentativas` e adia a linha
   (`proxima_tentativa_em` = agora + 1 s, 2 s, 4 s... até 5 min), guardando o `ultimo_erro`.
   - log-service fora do ar, 5xx, token recusado: o lote inteiro espera;
   - o log-service recusou o conteúdo do lote (`EntregaRecusada`, 4xx): o relay tenta os
     eventos um a um, e só o que for recusado sozinho fica para trás. Um evento ruim não trava
     a fila (ele sai da ordem, e o `ultimo_erro` diz por quê).

A tabela `outbox` não tem `empresa_id` (cada payload leva o seu) e não é `TemEmpresa`: o relay
lê eventos de todas as empresas sem passar pela rede de segurança de tenancy, e só ele faz isso.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.shared.domain.eventos import EventoDeNegocio
from app.shared.infrastructure.tipos import UUIDNativo

logger = logging.getLogger("nivelo.api.outbox")

LOTE_PADRAO = 100
INTERVALO_PADRAO_S = 1.0
BACKOFF_INICIAL_S = 1
BACKOFF_MAXIMO_S = 300


def atraso_da_tentativa(tentativas: int) -> int:
    """Segundos até a próxima tentativa depois de `tentativas` falhas: 1, 2, 4, ... até 300."""
    return int(min(BACKOFF_INICIAL_S * 2 ** max(tentativas - 1, 0), BACKOFF_MAXIMO_S))


class EntregaRecusada(Exception):
    """O destino recusou o conteúdo do lote (4xx de validação). Ao contrário de uma queda,
    tentar o mesmo lote de novo não adianta: o relay separa os eventos."""


class OutboxModel(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proxima_tentativa_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_erro: Mapped[str | None] = mapped_column(String(500), nullable=True)


@dataclass(frozen=True, slots=True)
class MetadadosDaRequisicao:
    """O que o evento leva da requisição e não do domínio."""

    ator_papel: str | None = None
    request_id: str | None = None


def _utc_sem_fuso(momento: datetime) -> datetime:
    return momento.astimezone(UTC).replace(tzinfo=None) if momento.tzinfo else momento


def payload_do_evento(evento: EventoDeNegocio, meta: MetadadosDaRequisicao) -> dict[str, Any]:
    """O formato único do evento de negócio (Parte A.4 do roteiro)."""
    return {
        "event_id": str(evento.event_id),
        "tipo": evento.tipo,
        "empresa_id": str(evento.empresa_id),
        "ator_id": evento.ator_id.valor,
        "ator_papel": meta.ator_papel,
        "recurso": evento.recurso,
        "recurso_id": evento.recurso_id,
        "ocorrido_em": _utc_sem_fuso(evento.ocorrido_em).isoformat(timespec="milliseconds") + "Z",
        "request_id": meta.request_id,
        "dados": evento.dados(),
    }


def gravar_na_outbox(session: Session, eventos: Iterable[EventoDeNegocio], meta: MetadadosDaRequisicao) -> int:
    """Acrescenta os eventos à transação corrente. Quem chama faz o commit."""
    n = 0
    for evento in eventos:
        session.add(
            OutboxModel(
                id=evento.event_id,
                tipo=evento.tipo,
                payload=payload_do_evento(evento, meta),
                ocorrido_em=_utc_sem_fuso(evento.ocorrido_em),
                tentativas=0,
            )
        )
        n += 1
    return n


Publicar = Callable[[list[dict[str, Any]]], None]


def _agora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class RelayDaOutbox:
    """Publica os eventos pendentes em lote. `publicar` recebe os payloads e levanta exceção
    se não conseguiu entregar o lote inteiro (`EntregaRecusada` se o conteúdo foi recusado)."""

    def __init__(
        self,
        fabrica_de_sessao: Callable[[], Session],
        publicar: Publicar,
        lote: int = LOTE_PADRAO,
        relogio: Callable[[], datetime] = _agora,
    ) -> None:
        self._fabrica = fabrica_de_sessao
        self._publicar = publicar
        self._lote = lote
        self._agora = relogio

    def publicar_pendentes(self) -> int:
        """Um ciclo: devolve quantos eventos foram publicados."""
        with self._fabrica() as session:
            agora = self._agora()
            consulta = (
                select(OutboxModel)
                .where(
                    OutboxModel.publicado_em.is_(None),
                    or_(OutboxModel.proxima_tentativa_em.is_(None), OutboxModel.proxima_tentativa_em <= agora),
                )
                .order_by(OutboxModel.ocorrido_em, OutboxModel.id)
                .limit(self._lote)
                # Com mais de um processo da API, cada relay pega linhas diferentes
                .with_for_update(skip_locked=True)
            )
            linhas = list(session.scalars(consulta))
            if not linhas:
                return 0
            try:
                self._publicar([linha.payload for linha in linhas])
                publicadas = linhas
            except EntregaRecusada:
                publicadas = self._um_a_um(linhas, agora)
            except Exception as erro:
                self._falhar(linhas, erro, agora)
                publicadas = []
            for linha in publicadas:
                linha.publicado_em = agora
                linha.ultimo_erro = None
            session.commit()
            return len(publicadas)

    def _um_a_um(self, linhas: list[OutboxModel], agora: datetime) -> list[OutboxModel]:
        publicadas: list[OutboxModel] = []
        for i, linha in enumerate(linhas):
            try:
                self._publicar([linha.payload])
            except EntregaRecusada as erro:
                self._falhar([linha], erro, agora)
                logger.error("relay da outbox: o log-service recusou o evento %s (%s)", linha.id, linha.tipo)
                continue
            except Exception as erro:
                # O destino caiu no meio: o resto do lote espera junto
                self._falhar(linhas[i:], erro, agora)
                break
            publicadas.append(linha)
        return publicadas

    def _falhar(self, linhas: list[OutboxModel], erro: Exception, agora: datetime) -> None:
        logger.warning(
            "relay da outbox: %d evento(s) não publicados (%s); nova tentativa com backoff", len(linhas), erro
        )
        for linha in linhas:
            linha.tentativas += 1
            linha.proxima_tentativa_em = agora + timedelta(seconds=atraso_da_tentativa(linha.tentativas))
            linha.ultimo_erro = f"{type(erro).__name__}: {erro}"[:500]

    def publicar_tudo(self) -> int:
        """Esvazia o que está pronto (ciclos seguidos até não sobrar pendente pronto)."""
        total = 0
        while (n := self.publicar_pendentes()) > 0:
            total += n
        return total


async def rodar_relay(relay: RelayDaOutbox, parar: asyncio.Event, intervalo_s: float = INTERVALO_PADRAO_S) -> None:
    """Laço do relay dentro da API (sem container novo). O banco é síncrono: cada ciclo roda
    numa thread, para não travar o event loop."""
    while not parar.is_set():
        try:
            await asyncio.to_thread(relay.publicar_tudo)
        except Exception:
            logger.exception("relay da outbox falhou neste ciclo")
        try:
            await asyncio.wait_for(parar.wait(), timeout=intervalo_s)
        except TimeoutError:
            pass
