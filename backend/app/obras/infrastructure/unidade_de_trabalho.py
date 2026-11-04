"""Unidade de trabalho SQLAlchemy de Gestão de Obras: uma transação na sessão do tenant.

- O commit grava os eventos dos agregados desta transação na `outbox`, na mesma transação
  (ADR 003). Sair sem commit, ou com erro, desfaz o dado e os eventos juntos.
- A transação do comando roda em READ COMMITTED (ADR 011). No REPEATABLE READ padrão do
  MariaDB, a transação que espera o `FOR UPDATE` da assinatura contaria as obras num retrato
  anterior ao commit da outra, e duas criações simultâneas passariam do limite do plano.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from app.assinaturas.application.direitos import ConsultaDireitos
from app.obras.domain.repositorio import RepositorioDeObras
from app.obras.infrastructure.repositorio import RepositorioDeObrasSQL
from app.shared.domain.eventos import EventoDeNegocio
from app.shared.domain.ids import EmpresaId
from app.shared.infrastructure.outbox import MetadadosDaRequisicao, gravar_na_outbox

ISOLAMENTO_DOS_COMANDOS = "READ COMMITTED"


class UnidadeDeTrabalhoDeObrasSQL:
    def __init__(
        self,
        session: Session,
        empresa_id: EmpresaId,
        direitos: ConsultaDireitos,
        metadados: MetadadosDaRequisicao | None = None,
    ) -> None:
        self._session = session
        self._metadados = metadados or MetadadosDaRequisicao()
        self._obras = RepositorioDeObrasSQL(session, empresa_id)
        self.obras: RepositorioDeObras = self._obras
        self.direitos: ConsultaDireitos = direitos

    def __enter__(self) -> Self:
        if self._session.get_bind().dialect.name in ("mysql", "mariadb"):
            # Precisa vir antes de qualquer comando da transação
            self._session.connection(execution_options={"isolation_level": ISOLAMENTO_DOS_COMANDOS})
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, erro: BaseException | None, rastro: TracebackType | None
    ) -> None:
        # Sem commit explícito (ou com erro), nada fica gravado
        self.rollback()

    def _eventos_pendentes(self) -> list[EventoDeNegocio]:
        eventos: list[EventoDeNegocio] = []
        for obra in self._obras.vistos.values():
            eventos.extend(obra.puxar_eventos())
        return sorted(eventos, key=lambda e: (e.ocorrido_em, e.event_id))

    def commit(self) -> None:
        gravar_na_outbox(self._session, self._eventos_pendentes(), self._metadados)
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
