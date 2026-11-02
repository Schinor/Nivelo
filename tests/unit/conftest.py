"""Testes unitários do domínio da API: sem banco, sem rede, sem FastAPI.

A suíte mistura os pacotes `app` da API e do auth-service no mesmo processo; a fixture
`api` garante que `app` seja o da API antes de importar o módulo pedido.
"""
import importlib
import os
import sys

import pytest

RAIZ_API = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))


@pytest.fixture
def api():
    for nome in list(sys.modules):
        if nome == "app" or nome.startswith("app."):
            del sys.modules[nome]
    if sys.path[0] != RAIZ_API:
        sys.path.insert(0, RAIZ_API)
    return importlib.import_module
