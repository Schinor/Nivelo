"""Porta do repositório de obras. A implementação recebe o `empresa_id` no construtor e o
aplica em toda consulta: não existe `obter(id)` sem tenant."""

from __future__ import annotations

from typing import Protocol

from app.obras.domain.ids import ObraId
from app.obras.domain.obra import Obra


class RepositorioDeObras(Protocol):
    def obter(self, obra_id: ObraId) -> Obra:
        """A obra da empresa do repositório, com os membros. Removida ou de outra empresa:
        `ObraNaoEncontrada`."""
        ...

    def adicionar(self, obra: Obra) -> None: ...

    def salvar(self, obra: Obra) -> None:
        """Grava as mudanças. Se os dados da obra mudaram, o UPDATE confere a `versao` lida e a
        incrementa; se outra transação mudou antes, `ConflitoDeVersao`."""
        ...

    def contar_ativas(self) -> int:
        """Obras com status ativa e não removidas: é o que o plano limita."""
        ...
