"""Outbox transacional dos eventos de negócio e o relay que os publica (ADR 003 e 012).

1. A unidade de trabalho chama `gravar_na_outbox` antes do commit: o agregado e os eventos
   dele entram na mesma transação. Se o dado foi gravado, o evento também foi.
2. O `RelayDaOutbox` lê as linhas sem `publicado_em`, publica em lote e marca a data. Se a
   publicação falhar, conta a tentativa e tenta de novo no próximo ciclo: a entrega é "pelo
   menos uma vez", e o log-service ignora `event_id` repetido.

A tabela `outbox` não tem `empresa_id` (cada payload leva o seu) e não é `TemEmpresa`: o relay
lê eventos de todas as empresas sem passar pela rede de segurança de tenancy, e só ele faz isso.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.shared.domain.eventos import EventoDeNegocio
from app.shared.infrastructure.tipos import UUIDNativo

logger = logging.getLogger("nivelo.api.outbox")

LOTE_PADRAO = 100
INTERVALO_PADRAO_S = 1.0


class OutboxModel(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


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


class RelayDaOutbox:
    """Publica os eventos pendentes em lote. `publicar` recebe os payloads e levanta exceção
    se não conseguiu entregar o lote inteiro."""

    def __init__(self, fabrica_de_sessao: Callable[[], Session], publicar: Publicar, lote: int = LOTE_PADRAO) -> None:
        self._fabrica = fabrica_de_sessao
        self._publicar = publicar
        self._lote = lote

    def publicar_pendentes(self) -> int:
        """Um ciclo: devolve quantos eventos foram publicados (0 se não havia ou se falhou)."""
        with self._fabrica() as session:
            consulta = (
                select(OutboxModel)
                .where(OutboxModel.publicado_em.is_(None))
                .order_by(OutboxModel.ocorrido_em, OutboxModel.id)
                .limit(self._lote)
                # Com mais de um processo da API, cada relay pega linhas diferentes
                .with_for_update(skip_locked=True)
            )
            linhas = list(session.scalars(consulta))
            if not linhas:
                return 0
            ids = [linha.id for linha in linhas]
            try:
                self._publicar([linha.payload for linha in linhas])
            except Exception:
                logger.warning(
                    "relay da outbox: %d evento(s) não publicados; nova tentativa no próximo ciclo", len(ids)
                )
                session.execute(
                    update(OutboxModel)
                    .where(OutboxModel.id.in_(ids))
                    .values(tentativas=OutboxModel.tentativas + 1)
                    .execution_options(synchronize_session=False)
                )
                session.commit()
                return 0
            session.execute(
                update(OutboxModel)
                .where(OutboxModel.id.in_(ids))
                .values(publicado_em=datetime.now(UTC).replace(tzinfo=None))
                .execution_options(synchronize_session=False)
            )
            session.commit()
            return len(ids)

    def publicar_tudo(self) -> int:
        """Esvazia a fila (ciclos seguidos até não sobrar pendente ou falhar)."""
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
