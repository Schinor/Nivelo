"""Abre a transação de um comando fora da unidade de trabalho (ADR 011)."""

from __future__ import annotations

from sqlalchemy.orm import Session


def abrir_transacao_de_comando(session: Session) -> None:
    """Descarta o retrato das leituras anteriores e abre a transação em READ COMMITTED: no
    REPEATABLE READ, o `FOR UPDATE` falha numa linha alterada depois daquele retrato."""
    session.rollback()
    if session.get_bind().dialect.name in ("mysql", "mariadb"):
        session.connection(execution_options={"isolation_level": "READ COMMITTED"})
