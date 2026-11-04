"""Porta do repositório de obras. A implementação recebe o `empresa_id` no construtor e o
aplica em toda consulta: não existe `obter(id)` sem tenant."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.obras.domain.diario import DiarioDeObra
from app.obras.domain.ids import DiarioId, FotoId, ObraId
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


class RepositorioDeDiarios(Protocol):
    """Diários da empresa do repositório. Como o de obras, não existe consulta sem tenant."""

    def obter(self, diario_id: DiarioId) -> DiarioDeObra:
        """O diário, com as fotos. De outra empresa ou inexistente: `DiarioNaoEncontrado`."""
        ...

    def obter_pela_foto(self, foto_id: FotoId) -> DiarioDeObra:
        """O diário que tem a foto. Foto de outra empresa ou inexistente: `FotoNaoEncontrada`."""
        ...

    def existe_na_data(self, obra_id: ObraId, data: date, exceto: DiarioId | None = None) -> bool: ...

    def adicionar(self, diario: DiarioDeObra) -> None:
        """Grava o diário novo. Outro diário da obra no mesmo dia: `DiarioDuplicado`."""
        ...

    def salvar(self, diario: DiarioDeObra) -> None:
        """Grava as mudanças (conteúdo, ocorrências, fotos, revisões e comentários novos) ou
        apaga o diário removido. Conteúdo alterado confere e incrementa a `versao`
        (`ConflitoDeVersao`)."""
        ...

    def contar_fotos_da_obra(self, obra_id: ObraId) -> int:
        """Fotos anexadas a todos os diários da obra: é o que o plano limita."""
        ...
