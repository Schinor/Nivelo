import os
import sys

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
        "origem": "api",
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
        "/eventos",
        json=_evento("diario_publicado", recurso="diario:13", ip="10.0.0.1"),
        headers={"X-Internal-Token": TOKEN},
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
    sem_acao = {"origem": "api", "timestamp": "2026-09-19T12:00:00+00:00"}
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


# ── Eventos de negócio (outbox da API, Fase 4b) ──────────────────────────────

EMPRESA_A = "0190f3a0-0000-7000-8000-00000000000a"
OBRA_A = "0190f3a0-0000-7000-8000-0000000000a1"


def _negocio(tipo, recurso="diario", recurso_id="0190f3a0-0000-7000-8000-0000000000d1", **extra):
    import uuid

    return {
        "event_id": str(uuid.uuid4()),
        "tipo": tipo,
        "empresa_id": EMPRESA_A,
        "ator_id": 2,
        "ator_papel": "encarregado",
        "recurso": recurso,
        "recurso_id": recurso_id,
        "ocorrido_em": "2026-11-04T14:02:11.000Z",
        "request_id": "req-1",
        "dados": {"obra_id": OBRA_A, "data": "2026-11-04"},
        **extra,
    }


def test_evento_de_negocio_vai_para_o_stream_com_ator_e_ocorrido_em():
    _, client = setup_log_service()
    headers = {"X-Internal-Token": TOKEN}
    ev = _negocio("diario.publicado")
    resp = client.post("/eventos/negocio", json={"eventos": [ev]}, headers=headers)
    assert resp.status_code == 202 and resp.json() == {"gravados": 1, "duplicados": 0}

    [gravado] = client.get("/eventos", headers=headers).json()
    assert gravado["event_id"] == ev["event_id"] and gravado["tipo"] == "diario.publicado"
    assert gravado["usuario_id"] == "2" and gravado["ator_papel"] == "encarregado"
    assert gravado["timestamp"] == "2026-11-04T14:02:11.000Z" and gravado["obra_id"] == OBRA_A
    assert gravado["acao"] == "diario.publicado" and gravado["recurso"] == f"diario:{ev['recurso_id']}"
    assert '"data":"2026-11-04"' in gravado["dados"]


def test_event_id_repetido_e_ignorado():
    _, client = setup_log_service()
    headers = {"X-Internal-Token": TOKEN}
    ev = _negocio("foto.anexada", recurso="foto")
    client.post("/eventos/negocio", json={"eventos": [ev]}, headers=headers)
    resp = client.post("/eventos/negocio", json={"eventos": [ev, _negocio("obra.criada")]}, headers=headers)
    assert resp.json() == {"gravados": 1, "duplicados": 1}
    assert len(client.get("/eventos", headers=headers).json()) == 2


def test_evento_de_negocio_exige_token_e_formato():
    _, client = setup_log_service()
    assert client.post("/eventos/negocio", json={"eventos": []}, headers={"X-Internal-Token": "x"}).status_code == 401
    sem_id = {k: v for k, v in _negocio("obra.criada").items() if k != "event_id"}
    resp = client.post("/eventos/negocio", json={"eventos": [sem_id]}, headers={"X-Internal-Token": TOKEN})
    assert resp.status_code == 422


def test_listagem_filtra_por_empresa_e_obra():
    _, client = setup_log_service()
    headers = {"X-Internal-Token": TOKEN}
    outra_obra = "0190f3a0-0000-7000-8000-0000000000a2"
    lote = [
        _negocio("obra.criada", recurso="obra", recurso_id=OBRA_A, dados={"nome": "Casa"}),
        _negocio("diario.publicado"),
        _negocio("diario.publicado", dados={"obra_id": outra_obra}),
        _negocio("obra.criada", recurso="obra", recurso_id=OBRA_A, empresa_id="outra-empresa"),
    ]
    client.post("/eventos/negocio", json={"eventos": lote}, headers=headers)
    client.post("/eventos", json=_evento("login"), headers=headers)  # evento técnico, sem empresa

    da_obra = client.get(f"/eventos?empresa_id={EMPRESA_A}&obra_id={OBRA_A}", headers=headers).json()
    assert [e["tipo"] for e in da_obra] == ["diario.publicado", "obra.criada"]
    da_empresa = client.get(f"/eventos?empresa_id={EMPRESA_A}&limit=2", headers=headers).json()
    assert len(da_empresa) == 2 and {e["empresa_id"] for e in da_empresa} == {EMPRESA_A}
