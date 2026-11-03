"""Erros de domínio de Gestão de Obras. O `codigo` vira o final do `type` do Problem Details."""

from __future__ import annotations

from app.shared.domain.erros import ErroDeDominio, RecursoNaoEncontrado


class ObraNaoEncontrada(RecursoNaoEncontrado):
    """Não existe, é de outra empresa, foi removida ou quem pede não é membro (404 nos quatro)."""

    def __init__(self) -> None:
        super().__init__("Obra não encontrada")


class DadoDaObraInvalido(ErroDeDominio):
    codigo = "obra-dado-invalido"


class PeriodoInvalido(ErroDeDominio):
    codigo = "obra-periodo-invalido"


class TransicaoDeStatusInvalida(ErroDeDominio):
    codigo = "obra-transicao-de-status-invalida"


class MembroInvalido(ErroDeDominio):
    codigo = "obra-membro-invalido"


class MembroDuplicado(ErroDeDominio):
    codigo = "obra-membro-duplicado"
    status = 409


class MembroNaoEncontrado(RecursoNaoEncontrado):
    def __init__(self) -> None:
        super().__init__("Essa pessoa não é membro da obra")
