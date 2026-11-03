"""Entrega da SPA pela API: arquivos do build, rotas do Angular, 404 da API e path traversal."""

import pytest
from test_backend_proxy import setup_api_app


@pytest.fixture
def spa(tmp_path):
    setup_api_app()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.shared.api.problem_details import registrar_handlers
    from app.shared.api.spa import registrar_spa

    build = tmp_path / "static"
    build.mkdir()
    (build / "index.html").write_text("<html>nivelo</html>")
    (build / "main.js").write_text("console.log('ok')")
    (tmp_path / "segredo.txt").write_text("SECRET_KEY=nao-pode-vazar")

    app = FastAPI()
    registrar_handlers(app)
    registrar_spa(app, str(build))
    return TestClient(app)


def test_arquivo_do_build_e_servido(spa):
    resp = spa.get("/main.js")
    assert resp.status_code == 200 and "console.log" in resp.text


@pytest.mark.parametrize("rota", ["/", "/login", "/obras/123"])
def test_rotas_do_angular_recebem_o_index(spa, rota):
    resp = spa.get(rota)
    assert resp.status_code == 200 and "nivelo" in resp.text


@pytest.mark.parametrize("rota", ["/api", "/api/nao-existe", "/api/obras/1/diarios"])
def test_rota_da_api_inexistente_e_404_em_problem_details(spa, rota):
    resp = spa.get(rota)
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
    assert "<html" not in resp.text


@pytest.mark.parametrize(
    "rota",
    [
        "/..%2fsegredo.txt",
        "/%2e%2e/segredo.txt",
        "/..%2f..%2f..%2f..%2f..%2fetc%2fpasswd",
        "/static/..%2f..%2fsegredo.txt",
    ],
)
def test_path_traversal_nao_le_arquivo_fora_do_build(spa, rota):
    resp = spa.get(rota)
    assert resp.status_code == 404
    assert "nao-pode-vazar" not in resp.text
    assert "root:" not in resp.text


def test_resolver_caminho_recusa_saida_do_diretorio(tmp_path):
    setup_api_app()
    from app.shared.api.spa import resolver_caminho

    assert resolver_caminho(str(tmp_path), "a/b.js") == str(tmp_path / "a" / "b.js")
    assert resolver_caminho(str(tmp_path), "../fora.txt") is None
    assert resolver_caminho(str(tmp_path), "/etc/passwd") is None
