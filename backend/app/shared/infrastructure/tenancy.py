"""Rede de segurança de tenancy no ORM (docs/adr/004).

Toda consulta ORM (SELECT, UPDATE, DELETE) que envolve um modelo `TemEmpresa` recebe o filtro
`empresa_id = <empresa da sessão>`. Uma consulta assim numa sessão **sem tenant definido falha**
em vez de devolver dados de todas as empresas. Inserções e alterações também são conferidas.

A empresa da sessão fica em `session.info["empresa_id"]`, preenchida pela dependência da API a
partir da `TenantContext` (que vem só do JWT). Exceções explícitas (painel admin, webhook do
Stripe, relay da outbox) usam `sem_tenant(session, motivo)`, revisadas em PR.

Os repositórios continuam recebendo o `empresa_id` no construtor: esta é a segunda camada.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, mapped_column, with_loader_criteria

from app.shared.infrastructure.tipos import UUIDNativo

CHAVE_EMPRESA = "empresa_id"
CHAVE_SEM_TENANT = "sem_tenant"


class TemEmpresa:
    """Mixin dos modelos ORM que pertencem a uma empresa: traz a coluna `empresa_id`."""

    empresa_id: Mapped[uuid.UUID] = mapped_column(UUIDNativo(), nullable=False)


class TenantNaoDefinido(RuntimeError):
    """Consulta ou gravação de dado de empresa numa sessão sem tenant."""


class TenantDivergente(RuntimeError):
    """Tentativa de gravar dado de uma empresa numa sessão de outra."""


def definir_tenant(session: Session, empresa_id: uuid.UUID) -> None:
    session.info[CHAVE_EMPRESA] = empresa_id
    session.info.pop(CHAVE_SEM_TENANT, None)


@contextmanager
def sem_tenant(session: Session, motivo: str) -> Iterator[Session]:
    """Libera a sessão do filtro de empresa. `motivo` documenta a exceção (aparece em revisão)."""
    if not motivo.strip():
        raise ValueError("informe o motivo para usar uma sessão sem tenant")
    anterior = session.info.get(CHAVE_SEM_TENANT)
    session.info[CHAVE_SEM_TENANT] = motivo
    try:
        yield session
    finally:
        if anterior is None:
            session.info.pop(CHAVE_SEM_TENANT, None)
        else:
            session.info[CHAVE_SEM_TENANT] = anterior


def _empresa_da_sessao(session: Session) -> uuid.UUID | None:
    if session.info.get(CHAVE_SEM_TENANT):
        return None
    empresa = session.info.get(CHAVE_EMPRESA)
    if empresa is None:
        raise TenantNaoDefinido("consulta a dado de empresa numa sessão sem tenant definido")
    return empresa  # type: ignore[no-any-return]


def _filtrar_por_empresa(estado: ORMExecuteState) -> None:
    if not (estado.is_select or estado.is_update or estado.is_delete):
        return
    if not any(issubclass(m.class_, TemEmpresa) for m in estado.all_mappers):
        return
    empresa = _empresa_da_sessao(estado.session)
    if empresa is None:
        return
    estado.statement = estado.statement.options(
        with_loader_criteria(TemEmpresa, lambda cls: cls.empresa_id == empresa, include_aliases=True)
    )


def _conferir_gravacoes(session: Session, _contexto: Any, _instancias: Any) -> None:
    objetos = [o for o in list(session.new) + list(session.dirty) if isinstance(o, TemEmpresa)]
    if not objetos:
        return
    empresa = _empresa_da_sessao(session)
    if empresa is None:
        return
    for obj in objetos:
        if obj.empresa_id is None:
            obj.empresa_id = empresa
        elif obj.empresa_id != empresa:
            raise TenantDivergente(f"{type(obj).__name__} de outra empresa numa sessão de {empresa}")


def ligar_rede_de_seguranca(alvo: type[Session] = Session) -> None:
    """Registra os eventos uma vez por classe de sessão (idempotente)."""
    if not event.contains(alvo, "do_orm_execute", _filtrar_por_empresa):
        event.listen(alvo, "do_orm_execute", _filtrar_por_empresa)
    if not event.contains(alvo, "before_flush", _conferir_gravacoes):
        event.listen(alvo, "before_flush", _conferir_gravacoes)


ligar_rede_de_seguranca()
