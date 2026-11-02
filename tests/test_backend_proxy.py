import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_12345678901234567890"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "1440"
os.environ["AUTH_SERVICE_URL"] = "http://auth-service:8001"


def setup_api_app():
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    sys.path.insert(0, os.path.abspath("backend"))

    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import Base, get_db
    from app.dependencies import current_user

    engine_test = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
    Base.metadata.create_all(bind=engine_test)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, TestingSessionLocal, current_user, TestClient


def test_api_sobe_com_docs_e_titulo_nivelo():
    app, _, _, TestClient = setup_api_app()
    client = TestClient(app)

    assert client.get("/api/docs").status_code == 200
    assert app.title == "Nivelo API"
    rotas = {r.path for r in app.routes}
    assert not any(r.startswith(("/api/filmes", "/api/favoritos", "/api/comentarios")) for r in rotas)


# ── Auditoria (log-service), /api/logs, logout, health e métricas ─────────────

def _usuario(uid, role, permissions):
    return {"id": uid, "nome": f"User {uid}", "email": f"u{uid}@teste.com", "role": role, "permissions": permissions}


def _capturar_eventos(monkeypatch):
    """Troca o cliente do log-service por um coletor em memória (chamar após setup_api_app)."""
    from app.clients import log_client

    eventos = []

    async def fake_registrar(acao, request=None, usuario_id=None, recurso=None, detalhes=None):
        eventos.append({"acao": acao, "usuario_id": usuario_id, "recurso": recurso, "detalhes": detalhes})

    monkeypatch.setattr(log_client, "registrar", fake_registrar)
    return eventos


def _mock_log_service(monkeypatch, handler):
    import httpx

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.routes.logs.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )


def _mock_dependencias_health(monkeypatch, auth_status=200, storage_status=403):
    """auth-service e Garage simulados; None = serviço fora do ar."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        codigo = auth_status if request.url.host == "auth-service" else storage_status
        if codigo is None:
            raise httpx.ConnectError("sem rota", request=request)
        return httpx.Response(codigo)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.main.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )


def test_health_e_metrics_da_api(monkeypatch):
    app, _, _, TestClient = setup_api_app()
    _mock_dependencias_health(monkeypatch)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "healthy", "db": "up", "auth_service": "up", "storage": "up"}

    client.get("/api/docs")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text
    assert "http_request_duration_seconds" in metrics.text


def test_health_retorna_503_quando_banco_cai(monkeypatch):
    app, _, _, TestClient = setup_api_app()
    import app.main as main_mod

    class BancoFora:
        def connect(self):
            raise RuntimeError("banco indisponível")

    _mock_dependencias_health(monkeypatch)
    monkeypatch.setattr(main_mod, "engine", BancoFora())
    resp = TestClient(app).get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "unhealthy"
    assert resp.json()["db"] == "down"


@pytest.mark.parametrize(
    "auth_status, storage_status, campo",
    [(None, 403, "auth_service"), (503, 403, "auth_service"), (200, None, "storage"), (200, 502, "storage")],
)
def test_health_retorna_503_quando_auth_service_ou_storage_caem(monkeypatch, auth_status, storage_status, campo):
    app, _, _, TestClient = setup_api_app()
    _mock_dependencias_health(monkeypatch, auth_status=auth_status, storage_status=storage_status)

    resp = TestClient(app).get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "unhealthy"
    assert resp.json()[campo] == "down"


def test_403_repassado_do_auth_service_tambem_gera_acesso_negado(monkeypatch):
    from fastapi import HTTPException
    from jose import jwt

    app, _, _, TestClient = setup_api_app()
    eventos = _capturar_eventos(monkeypatch)

    async def auth_nega(method, path, **kw):
        raise HTTPException(status_code=403, detail="Acesso negado: permissão 'gerenciar:usuarios' necessária")

    monkeypatch.setattr("app.routes.auth.forward_request", auth_nega)
    token = jwt.encode({"sub": "5"}, os.environ["SECRET_KEY"], algorithm="HS256")

    resp = TestClient(app).get("/api/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert eventos == [
        {"acao": "acesso_negado", "usuario_id": 5, "recurso": None, "detalhes": "GET /api/auth/users"}
    ]


def test_api_logs_usuario_comum_recebe_403_e_gera_acesso_negado(monkeypatch):
    app, _, current_user, TestClient = setup_api_app()
    eventos = _capturar_eventos(monkeypatch)
    client = TestClient(app)

    app.dependency_overrides[current_user] = lambda: _usuario(
        7, "houston-temos-acesso", ["listar:favoritos", "criar:comentarios"]
    )

    resp = client.get("/api/logs")
    assert resp.status_code == 403
    assert eventos == [
        {"acao": "acesso_negado", "usuario_id": 7, "recurso": "visualizar:logs", "detalhes": "GET /api/logs"}
    ]


def test_api_logs_admin_lista_eventos_do_log_service(monkeypatch):
    import httpx

    app, _, current_user, TestClient = setup_api_app()
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(200, json=[{"id": "2-0", "acao": "logout"}, {"id": "1-0", "acao": "login"}])

    _mock_log_service(monkeypatch, handler)
    app.dependency_overrides[current_user] = lambda: _usuario(1, "admin", ["visualizar:logs"])

    resp = TestClient(app).get("/api/logs?limit=20")
    assert resp.status_code == 200
    assert [e["acao"] for e in resp.json()] == ["logout", "login"]
    assert chamadas[0].url.params["limit"] == "20"
    assert "x-internal-token" in chamadas[0].headers


def test_api_logs_retorna_503_se_log_service_estiver_fora(monkeypatch):
    import httpx

    app, _, current_user, TestClient = setup_api_app()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota", request=request)

    _mock_log_service(monkeypatch, handler)
    app.dependency_overrides[current_user] = lambda: _usuario(1, "admin", ["administrar:sistema"])

    resp = TestClient(app).get("/api/logs")
    assert resp.status_code == 503






def test_login_e_login_falhou_geram_eventos(monkeypatch):
    from fastapi import HTTPException

    app, _, _, TestClient = setup_api_app()
    eventos = _capturar_eventos(monkeypatch)
    client = TestClient(app)

    async def login_ok(method, path, **kw):
        return {"access_token": "t", "token_type": "bearer", "user": {"id": 42, "nome": "A", "email": "a@a.com"}}

    monkeypatch.setattr("app.routes.auth.forward_request", login_ok)
    assert client.post("/api/auth/login", data={"username": "a@a.com", "password": "x"}).status_code == 200
    assert eventos[-1]["acao"] == "login"
    assert eventos[-1]["usuario_id"] == 42

    async def login_401(method, path, **kw):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")

    monkeypatch.setattr("app.routes.auth.forward_request", login_401)
    assert client.post("/api/auth/login", data={"username": "b@b.com", "password": "x"}).status_code == 401
    assert eventos[-1]["acao"] == "login_falhou"
    assert eventos[-1]["usuario_id"] is None
    assert eventos[-1]["detalhes"] == "email:b@b.com"


def test_logout_exige_jwt_e_registra_evento(monkeypatch):
    app, _, current_user, TestClient = setup_api_app()
    eventos = _capturar_eventos(monkeypatch)
    client = TestClient(app)

    assert client.post("/api/auth/logout").status_code == 401
    assert eventos == []

    app.dependency_overrides[current_user] = lambda: _usuario(5, "admin", ["administrar:sistema"])
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204
    assert eventos == [{"acao": "logout", "usuario_id": 5, "recurso": None, "detalhes": None}]




def test_cliente_de_log_nunca_levanta_excecao_com_log_service_fora():
    import asyncio

    setup_api_app()
    from app.clients import log_client
    from app.core.config import settings

    settings.LOG_SERVICE_URL = "http://127.0.0.1:9"  # porta fechada
    asyncio.run(log_client.registrar("teste"))  # não deve levantar


def _mock_grafana(monkeypatch, handler):
    import httpx

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.routes.observability_proxy.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )


def test_proxy_grafana_preserva_host_e_headers_com_acento(monkeypatch):
    import httpx

    app, _, _, TestClient = setup_api_app()
    recebidos = {}

    def handler(request):
        recebidos.update({k.decode(): v for k, v in request.headers.raw})
        return httpx.Response(200, json={"results": {}})

    _mock_grafana(monkeypatch, handler)
    client = TestClient(app, base_url="https://filmes.exemplo.com")

    resp = client.post(
        "/grafana/api/ds/query",
        json={"queries": []},
        headers={
            "Origin": "https://filmes.exemplo.com",
            # O Grafana manda o título do painel num header, com acentos em UTF-8
            "X-Panel-Title": "Latência p95".encode(),
            "X-Forwarded-For": "203.0.113.7",
        },
    )

    assert resp.status_code == 200
    # Sem o Host original, o CSRF do Grafana compara Origin com "grafana:3000" e recusa (403)
    assert recebidos["host"] == b"filmes.exemplo.com"
    assert recebidos["x-forwarded-host"] == b"filmes.exemplo.com"
    assert recebidos["x-forwarded-for"].startswith(b"203.0.113.7, ")
    assert recebidos["x-panel-title"] == "Latência p95".encode()


def test_proxy_grafana_repassa_todos_os_set_cookie(monkeypatch):
    import httpx

    app, _, _, TestClient = setup_api_app()

    def handler(request):
        return httpx.Response(
            200,
            headers=[
                ("set-cookie", "grafana_session=abc; Path=/; HttpOnly"),
                ("set-cookie", "grafana_session_expiry=123; Path=/"),
            ],
            json={"message": "Logged in"},
        )

    _mock_grafana(monkeypatch, handler)
    resp = TestClient(app).post("/grafana/login", json={"user": "admin", "password": "x"})

    assert resp.status_code == 200
    assert resp.headers.get_list("set-cookie") == [
        "grafana_session=abc; Path=/; HttpOnly",
        "grafana_session_expiry=123; Path=/",
    ]
