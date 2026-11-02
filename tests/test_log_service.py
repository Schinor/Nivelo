import os
import sys

import pytest

TOKEN = "token-interno-de-teste"


def setup_log_service():
    """Importa o log-service isolado dos demais pacotes 'app' e troca o Redis por fakeredis."""
    os.environ["LOG_INTERNAL_TOKEN"] = TOKEN
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"

    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]
    sys.path.insert(0, os.path.abspath("log-service"))

    import fakeredis
    from fastapi.testclient import TestClient
    import app.main as main_mod

    servidor = fakeredis.FakeServer()
    main_mod.r = fakeredis.FakeAsyncRedis(server=servidor, decode_responses=True)
    return main_mod, TestClient(main_mod.app)


def _evento(acao, usuario_id=1, **extra):
    return {
        "usuario_id": usuario_id,
        "acao": acao,
        "origem": "catalogo",
        "timestamp": "2026-09-19T12:00:00+00:00",
        **extra,
    }


def test_post_sem_token_retorna_401_ou_422():
    _, client = setup_log_service()
    assert client.post("/eventos", json=_evento("login")).status_code == 422  # header obrigatório ausente
    resp = client.post("/eventos", json=_evento("login"), headers={"X-Internal-Token": "errado"})
    assert resp.status_code == 401


def test_post_com_token_retorna_202_e_grava_no_stream():
    main_mod, client = setup_log_service()
    resp = client.post(
        "/eventos", json=_evento("diario_publicado", recurso="diario:13", ip="10.0.0.1"), headers={"X-Internal-Token": TOKEN}
    )
    assert resp.status_code == 202

    lista = client.get("/eventos", headers={"X-Internal-Token": TOKEN}).json()
    assert len(lista) == 1
    assert lista[0]["acao"] == "diario_publicado"
    assert lista[0]["usuario_id"] == "1"
    assert lista[0]["recurso"] == "diario:13"
    assert lista[0]["ip"] == "10.0.0.1"
    assert "id" in lista[0]


def test_get_ordena_do_mais_recente_para_o_mais_antigo_e_respeita_limit():
    _, client = setup_log_service()
    headers = {"X-Internal-Token": TOKEN}
    for acao in ["login", "obra_criada", "diario_publicado", "logout"]:
        assert client.post("/eventos", json=_evento(acao), headers=headers).status_code == 202

    todos = client.get("/eventos", headers=headers).json()
    assert [e["acao"] for e in todos] == ["logout", "diario_publicado", "obra_criada", "login"]

    dois = client.get("/eventos?limit=2", headers=headers).json()
    assert [e["acao"] for e in dois] == ["logout", "diario_publicado"]


def test_get_exige_token_e_valida_limit():
    _, client = setup_log_service()
    assert client.get("/eventos", headers={"X-Internal-Token": "errado"}).status_code == 401
    assert client.get("/eventos?limit=0", headers={"X-Internal-Token": TOKEN}).status_code == 422


def test_evento_invalido_e_rejeitado():
    _, client = setup_log_service()
    sem_acao = {"origem": "catalogo", "timestamp": "2026-09-19T12:00:00+00:00"}
    assert client.post("/eventos", json=sem_acao, headers={"X-Internal-Token": TOKEN}).status_code == 422


def test_health_reflete_o_estado_do_redis():
    main_mod, client = setup_log_service()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "redis": "up"}

    class RedisFora:
        async def ping(self):
            raise ConnectionError("redis fora do ar")

    main_mod.r = RedisFora()
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json() == {"status": "unhealthy", "redis": "down"}


def test_metrics_expostas():
    _, client = setup_log_service()
    client.get("/eventos", headers={"X-Internal-Token": TOKEN})
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text
