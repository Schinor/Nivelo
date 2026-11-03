"""Erros de domínio base. A camada de API traduz cada um para Problem Details.

Cada erro diz o próprio `status` HTTP e o `codigo` (o final do `type` estável), e pode levar
campos extras para o corpo da resposta. O domínio não conhece HTTP: o número é só um rótulo
que a borda usa, como o `codigo`.
"""

from __future__ import annotations

from typing import ClassVar


class ErroDeDominio(Exception):
    """Regra de negócio violada. `codigo` vira o final do `type` do Problem Details."""

    codigo: ClassVar[str] = "regra-de-negocio"
    status: ClassVar[int] = 422
    titulo: str | None = None

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem

    def extras(self) -> dict[str, object]:
        """Campos a mais no corpo do Problem Details (ex.: limite e uso do plano)."""
        return {}


class RecursoNaoEncontrado(ErroDeDominio):
    """Não existe, ou é de outra empresa: as duas situações respondem igual (404)."""

    codigo = "nao-encontrado"
    status = 404


class ConflitoDeVersao(ErroDeDominio):
    """Concorrência otimista: alguém alterou o recurso depois que ele foi lido (409)."""

    codigo = "conflito-de-versao"
    status = 409

    def __init__(
        self,
        versao_atual: int | None = None,
        mensagem: str = "Outra pessoa alterou este registro depois que você abriu. Recarregue e tente de novo.",
    ) -> None:
        super().__init__(mensagem)
        self.versao_atual = versao_atual

    def extras(self) -> dict[str, object]:
        return {} if self.versao_atual is None else {"versao_atual": self.versao_atual}
