"""Erros de domínio base. A camada de API traduz cada um para Problem Details."""


class ErroDeDominio(Exception):
    """Regra de negócio violada. `codigo` vira o final do `type` do Problem Details."""

    codigo = "regra-de-negocio"

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class RecursoNaoEncontrado(ErroDeDominio):
    """Não existe, ou é de outra empresa: as duas situações respondem igual (404)."""

    codigo = "nao-encontrado"
