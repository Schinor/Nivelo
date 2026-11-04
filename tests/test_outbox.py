"""Outbox e relay (ADR 003 e 012): o evento é gravado na mesma transação do comando e o relay
o entrega ao log-service, que o põe no Redis Stream."""

import uuid

import pytest
from test_autenticacao_api import auth, token

pytestmark = pytest.mark.mariadb

EMPRESA_A = "0190f3a0-0000-7000-8000-00000000000a"
DONO = auth(token("1", empresa_id=EMPRESA_A, papel="dono"))
OBRA = {
    "nome": "Casa do Jorge",
    "endereco": {"logradouro": "Rua 1", "cidade": "Marília", "uf": "SP"},
    "cliente_nome": "Jorge",
    "data_inicio": "2026-11-03",
    "previsao_termino": "2027-03-31",
}


@pytest.fixture
def api():
    from test_backend_proxy import setup_api_app

    app, SessionLocal, _, TestClient = setup_api_app()

    class Api:
        pass

    a = Api()
    a.client, a.SessionLocal = TestClient(app), SessionLocal
    return a


def _outbox(api):
    from sqlalchemy import select

    from app.shared.infrastructure.outbox import OutboxModel

    with api.SessionLocal() as s:
        return list(s.scalars(select(OutboxModel).order_by(OutboxModel.ocorrido_em)))


def test_comando_grava_o_evento_na_outbox_no_formato_unico(api):
    resp = api.client.post("/api/obras", json=OBRA, headers={**DONO, "X-Request-ID": "req-obra-1"})
    assert resp.status_code == 201
    [linha] = _outbox(api)
    assert linha.tipo == "obra.criada" and linha.publicado_em is None and linha.tentativas == 0
    p = linha.payload
    assert p["event_id"] == str(linha.id)
    assert (p["tipo"], p["empresa_id"], p["ator_id"], p["ator_papel"]) == ("obra.criada", EMPRESA_A, 1, "dono")
    assert (p["recurso"], p["recurso_id"], p["request_id"]) == ("obra", resp.json()["id"], "req-obra-1")
    assert p["ocorrido_em"].endswith("Z") and p["dados"] == {"nome": "Casa do Jorge"}


def test_comando_recusado_nao_deixa_evento(api):
    assert api.client.post("/api/obras", json=OBRA, headers=DONO).status_code == 201
    assert api.client.post("/api/obras", json={**OBRA, "nome": "Segunda"}, headers=DONO).status_code == 402
    assert [linha.tipo for linha in _outbox(api)] == ["obra.criada"]


def test_cada_comando_grava_os_proprios_eventos(api):
    obra = api.client.post("/api/obras", json=OBRA, headers=DONO).json()
    api.client.patch(f"/api/obras/{obra['id']}/status", json={"status": "pausada"}, headers=DONO)
    api.client.delete(f"/api/obras/{obra['id']}", headers=DONO)
    assert [linha.tipo for linha in _outbox(api)] == ["obra.criada", "obra.status_alterado", "obra.removida"]


def test_relay_publica_marca_e_numa_falha_conta_a_tentativa_e_tenta_de_novo(api):
    from app.shared.infrastructure.outbox import RelayDaOutbox

    api.client.post("/api/obras", json=OBRA, headers=DONO)
    entregues, falhar = [], [True]

    def publicar(lote):
        if falhar[0]:
            raise ConnectionError("log-service fora do ar")
        entregues.extend(lote)

    relay = RelayDaOutbox(api.SessionLocal, publicar)
    assert relay.publicar_tudo() == 0
    [linha] = _outbox(api)
    assert linha.publicado_em is None and linha.tentativas == 1

    falhar[0] = False
    assert relay.publicar_tudo() == 1
    assert [e["tipo"] for e in entregues] == ["obra.criada"]
    [linha] = _outbox(api)
    assert linha.publicado_em is not None
    assert relay.publicar_tudo() == 0  # nada pendente: não republica


def test_relay_publica_em_lotes_na_ordem_em_que_aconteceram(api):
    from datetime import datetime, timedelta

    from app.shared.infrastructure.outbox import OutboxModel, RelayDaOutbox

    inicio = datetime(2026, 11, 4, 12, 0)
    with api.SessionLocal() as s:
        for i in reversed(range(5)):
            eid = uuid.uuid4()
            s.add(
                OutboxModel(
                    id=eid,
                    tipo=f"teste.evento_{i}",
                    payload={"event_id": str(eid), "i": i},
                    ocorrido_em=inicio + timedelta(seconds=i),
                    tentativas=0,
                )
            )
        s.commit()
    lotes = []
    assert RelayDaOutbox(api.SessionLocal, lotes.append, lote=2).publicar_tudo() == 5
    assert [[e["i"] for e in lote] for lote in lotes] == [[0, 1], [2, 3], [4]]


def test_eventos_chegam_ao_redis_stream_com_ator_e_ocorrido_em(api):
    """Ponta a ponta: comando → outbox → relay → log-service → Redis Stream."""
    from app.shared.infrastructure.outbox import RelayDaOutbox

    api.client.post("/api/obras", json=OBRA, headers=DONO)
    lote = []
    RelayDaOutbox(api.SessionLocal, lote.extend).publicar_tudo()

    from test_log_service import TOKEN, setup_log_service

    _, log = setup_log_service()
    headers = {"X-Internal-Token": TOKEN}
    assert log.post("/eventos/negocio", json={"eventos": lote}, headers=headers).json()["gravados"] == 1
    assert log.post("/eventos/negocio", json={"eventos": lote}, headers=headers).json()["duplicados"] == 1
    [no_stream] = log.get("/eventos", headers=headers).json()
    assert no_stream["tipo"] == "obra.criada" and no_stream["usuario_id"] == "1"
    assert no_stream["timestamp"] == lote[0]["ocorrido_em"] and no_stream["empresa_id"] == EMPRESA_A


def test_publicador_entrega_o_lote_ao_log_service_com_o_token_interno(api, monkeypatch):
    import httpx

    from app.shared.infrastructure.log_service import PublicadorNoLogService

    pedidos = []

    def fake_post(url, json=None, headers=None, timeout=None):
        pedidos.append({"url": url, "json": json, "headers": headers})
        return httpx.Response(202, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.shared.infrastructure.log_service.httpx.post", fake_post)
    PublicadorNoLogService(url="http://log-service:8002", token="segredo")([{"event_id": "x"}])
    assert pedidos == [
        {
            "url": "http://log-service:8002/eventos/negocio",
            "json": {"eventos": [{"event_id": "x"}]},
            "headers": {"X-Internal-Token": "segredo"},
        }
    ]

    def recusa(url, **kw):
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.shared.infrastructure.log_service.httpx.post", recusa)
    with pytest.raises(httpx.HTTPStatusError):
        PublicadorNoLogService(url="http://log-service:8002", token="segredo")([{"event_id": "x"}])


def test_laco_do_relay_roda_ate_mandarem_parar(api):
    import asyncio

    from app.shared.infrastructure.outbox import RelayDaOutbox, rodar_relay

    api.client.post("/api/obras", json=OBRA, headers=DONO)
    entregues = []

    async def rodar():
        parar = asyncio.Event()

        def publicar(lote):
            entregues.extend(lote)
            parar.set()

        await asyncio.wait_for(rodar_relay(RelayDaOutbox(api.SessionLocal, publicar), parar, 0.01), timeout=5)

    asyncio.run(rodar())
    assert [e["tipo"] for e in entregues] == ["obra.criada"]


def test_eventos_do_mesmo_segundo_saem_na_ordem_em_que_aconteceram(api):
    """O MariaDB guarda `ocorrido_em` sem fração de segundo: o desempate é o event_id (UUID v7
    monotônico), e não a sorte."""
    from datetime import UTC, datetime

    from app.shared.domain.eventos import EventoDeNegocio
    from app.shared.domain.ids import EmpresaId, UsuarioId
    from app.shared.infrastructure.outbox import MetadadosDaRequisicao, RelayDaOutbox, gravar_na_outbox

    class Teste(EventoDeNegocio):
        recurso = "teste"

        @property
        def recurso_id(self):
            return "x"

    mesmo_segundo = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)
    eventos = [
        Teste(tipo=f"teste.n{i:02d}", empresa_id=EmpresaId(uuid.UUID(EMPRESA_A)), ator_id=UsuarioId(1),
              ocorrido_em=mesmo_segundo)
        for i in range(40)
    ]  # fmt: skip
    with api.SessionLocal() as s:
        gravar_na_outbox(s, reversed(eventos), MetadadosDaRequisicao())  # a ordem de gravação não importa
        s.commit()
    entregues = []
    RelayDaOutbox(api.SessionLocal, entregues.extend, lote=7).publicar_tudo()
    assert [e["tipo"] for e in entregues] == [e.tipo for e in eventos]
