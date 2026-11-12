"""A API só sobe com a chave de teste do Stripe.

As chaves são montadas por partes para a busca por segredos do repositório continuar vazia.
"""

import pytest


def _chave(tipo: str, modo: str) -> str:
    return "_".join((tipo, modo, "51Abc"))


@pytest.fixture
def criar(api):
    config = api("app.core.config")
    return lambda chave: config.Settings(DATABASE_URL="sqlite://", SECRET_KEY="x", STRIPE_SECRET_KEY=chave)


@pytest.mark.parametrize("tipo", ["sk", "rk"])
def test_recusa_chave_de_producao(criar, tipo):
    with pytest.raises(ValueError, match="só aceita a chave de teste"):
        criar(_chave(tipo, "live"))


@pytest.mark.parametrize("chave", [_chave("sk", "test"), _chave("rk", "test"), ""])
def test_aceita_chave_de_teste_ou_vazia(criar, chave):
    assert criar(chave).STRIPE_SECRET_KEY == chave
