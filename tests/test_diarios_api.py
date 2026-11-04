"""Fase 4b: diários, ocorrências, revisões, fotos e comentários pela API, com JWT de verdade.

Dados (tests/conftest.py): empresa A com as obras A1 (encarregados ENC_A e MULTI) e A2 (cliente
CLI_A); empresa B com B1. O relógio é fixo em 04/11/2026 e o storage é simulado em memória.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from conftest import CLI_A, DONO_A, DONO_B, EMPRESA_A, EMPRESA_B, ENC_A, MULTI, OBRA_A1, OBRA_A2, OBRA_B1
from test_obras_api import tk

# Tenancy, papéis e plano: rodam também no MariaDB (tests/banco_de_teste.py)
pytestmark = pytest.mark.mariadb

DONO = tk(DONO_A, EMPRESA_A, "dono")
ENC = tk(ENC_A, EMPRESA_A, "encarregado")
OUTRO_ENC = tk(MULTI, EMPRESA_A, "encarregado")
CLI = tk(CLI_A, EMPRESA_A, "cliente")
DONO_DE_B = tk(DONO_B, EMPRESA_B, "dono")

HOJE = date(2026, 11, 4)
DIARIO = {
    "data": "2026-11-03",
    "clima": {"manha": "ensolarado", "tarde": "chuvoso"},
    "condicao": "praticavel",
    "atividades": "Contrapiso da cozinha",
    "efetivo": 4,
    "ocorrencias": [{"tipo": "chuva", "descricao": "Chuva às 15h", "impacto_prazo_dias": 0}],
}


class RelogioFixo:
    def agora(self):
        return datetime(2026, 11, 4, 18, 0, tzinfo=UTC)

    def hoje(self):
        return HOJE


class StorageFalso:
    """O bucket em memória: `objetos[chave] = (tamanho, content_type)`."""

    def __init__(self):
        self.objetos = {}
        self.apagados = []

    def url_para_enviar(self, chave, content_type, validade_s):
        return f"/storage/bucket/{chave}?X-Amz-Expires={validade_s}&X-Amz-Signature=put"

    def metadados(self, chave):
        from app.obras.application.portas import MetadadosDoObjeto

        if chave not in self.objetos:
            return None
        tamanho, tipo = self.objetos[chave]
        return MetadadosDoObjeto(tamanho_bytes=tamanho, content_type=tipo)

    def url_para_ler(self, chave, validade_s):
        return f"/storage/bucket/{chave}?X-Amz-Expires={validade_s}&X-Amz-Signature=get"

    def apagar(self, chave):
        self.objetos.pop(chave, None)
        self.apagados.append(chave)


class HistoricoFalso:
    def __init__(self):
        self.pedidos = []

    def eventos(self, ctx, obra_id, limite):
        self.pedidos.append((str(ctx.empresa_id), str(obra_id), limite))
        return [{"event_id": "e1", "tipo": "obra.criada", "ator_id": 1, "dados": {"nome": "Casa"}}]


@pytest.fixture
def ctx(obras_ctx):
    from app.main import app
    from app.obras.api import dependencias

    obras_ctx.storage, obras_ctx.historico = StorageFalso(), HistoricoFalso()
    app.dependency_overrides[dependencias.relogio] = RelogioFixo
    app.dependency_overrides[dependencias.armazenamento_de_fotos] = lambda: obras_ctx.storage
    app.dependency_overrides[dependencias.historico_da_obra] = lambda: obras_ctx.historico
    yield obras_ctx
    for dep in (dependencias.relogio, dependencias.armazenamento_de_fotos, dependencias.historico_da_obra):
        app.dependency_overrides.pop(dep, None)


def registrar(ctx, obra=OBRA_A1, quem=ENC, **mudancas):
    return ctx.client.post(f"/api/obras/{obra}/diarios", json={**DIARIO, **mudancas}, headers=quem)


def novo(ctx, obra=OBRA_A1, quem=ENC, **mudancas):
    resp = registrar(ctx, obra, quem, **mudancas)
    assert resp.status_code == 201, resp.text
    return resp.json()


def publicar(ctx, diario, quem=ENC):
    resp = ctx.client.post(f"/api/diarios/{diario['id']}/publicar", headers=quem)
    assert resp.status_code == 200, resp.text
    return resp.json()


def editar(ctx, diario, quem=ENC, versao=None, **mudancas):
    corpo = {**DIARIO, **mudancas, "versao": versao or diario["versao"]}
    return ctx.client.put(f"/api/diarios/{diario['id']}", json=corpo, headers=quem)


def outbox(ctx):
    from sqlalchemy import select

    from app.shared.infrastructure.outbox import OutboxModel

    with ctx.SessionLocal() as s:
        return [o.payload for o in s.scalars(select(OutboxModel).order_by(OutboxModel.ocorrido_em, OutboxModel.id))]


# ── Registro ─────────────────────────────────────────────────────────────────


def test_encarregado_registra_diario_rascunho_na_sua_obra(ctx):
    resp = registrar(ctx)
    assert resp.status_code == 201, resp.text
    d = resp.json()
    assert resp.headers["Location"] == f"/api/diarios/{d['id']}" and resp.headers["ETag"] == '"1"'
    assert (d["status"], d["versao"], d["autor_id"], d["obra_id"]) == ("rascunho", 1, ENC_A, OBRA_A1)
    assert d["clima"] == {"manha": "ensolarado", "tarde": "chuvoso"} and d["efetivo"] == 4
    assert [o["tipo"] for o in d["ocorrencias"]] == ["chuva"] and d["fotos"] == [] and d["revisoes"] == 0
    eventos = outbox(ctx)
    assert [e["tipo"] for e in eventos] == ["diario.registrado", "ocorrencia.registrada"]
    assert eventos[0]["ator_papel"] == "encarregado" and eventos[0]["dados"]["obra_id"] == OBRA_A1


def test_um_diario_por_obra_por_dia(ctx):
    novo(ctx)
    resp = registrar(ctx, quem=DONO)
    assert resp.status_code == 409 and resp.json()["type"] == "https://nivelo/erros/diario-duplicado"
    assert registrar(ctx, OBRA_A2, DONO).status_code == 201  # outra obra no mesmo dia pode


def test_diario_de_dia_futuro_e_recusado(ctx):
    resp = registrar(ctx, data="2026-11-05")
    assert resp.status_code == 422 and resp.json()["type"] == "https://nivelo/erros/diario-data-futura"
    assert registrar(ctx, data="2026-11-04").status_code == 201  # hoje vale


def test_dado_invalido_e_422(ctx):
    assert registrar(ctx, efetivo=-1).status_code == 422
    assert registrar(ctx, clima={"manha": "granizo"}).status_code == 422
    assert registrar(ctx, ocorrencias=[{"tipo": "enchente", "descricao": "x"}]).status_code == 422


def test_encarregado_so_registra_nas_obras_em_que_e_membro(ctx):
    assert registrar(ctx, OBRA_A2, ENC).status_code == 404
    assert registrar(ctx, "0190f3a0-0000-7000-8000-0000000000a9", DONO).status_code == 404  # obra removida


@pytest.mark.parametrize(
    "metodo, rota",
    [
        ("put", "/api/diarios/{d}"),
        ("post", "/api/diarios/{d}/publicar"),
        ("post", "/api/diarios/{d}/fotos/upload-url"),
        ("post", "/api/diarios/{d}/fotos"),
        ("delete", "/api/diarios/{d}"),
    ],
)
def test_cliente_nao_escreve_em_diario_e_o_403_e_auditado(ctx, metodo, rota):
    d = novo(ctx, OBRA_A2, DONO)
    publicar(ctx, d, DONO)
    resp = getattr(ctx.client, metodo)(
        rota.format(d=d["id"]), headers=CLI, **({} if metodo == "delete" else {"json": {}})
    )
    assert resp.status_code == 403
    assert ctx.eventos[-1]["acao"] == "acesso.negado" and ctx.eventos[-1]["usuario_id"] == CLI_A


def test_so_o_dono_remove_diario(ctx):
    d = novo(ctx)
    assert ctx.client.delete(f"/api/diarios/{d['id']}", headers=ENC).status_code == 403


# ── Visibilidade e tenancy ───────────────────────────────────────────────────


def test_cliente_nao_ve_rascunho_e_ve_o_publicado(ctx):
    rascunho = novo(ctx, OBRA_A2, DONO, data="2026-11-02")
    pub = publicar(ctx, novo(ctx, OBRA_A2, DONO), DONO)

    lista = ctx.client.get(f"/api/obras/{OBRA_A2}/diarios", headers=CLI).json()
    assert [d["id"] for d in lista["itens"]] == [pub["id"]] and lista["total"] == 1
    assert ctx.client.get(f"/api/diarios/{rascunho['id']}", headers=CLI).status_code == 404
    assert ctx.client.get(f"/api/diarios/{pub['id']}", headers=CLI).json()["status"] == "publicado"
    assert ctx.client.get(f"/api/obras/{OBRA_A2}/diarios", headers=DONO).json()["total"] == 2


def test_encarregado_nao_ve_diario_de_obra_em_que_nao_e_membro(ctx):
    d = novo(ctx, OBRA_A2, DONO)
    assert ctx.client.get(f"/api/diarios/{d['id']}", headers=ENC).status_code == 404
    assert ctx.client.get(f"/api/obras/{OBRA_A2}/diarios", headers=ENC).status_code == 404


def test_b_abrindo_diario_de_a_recebe_404_e_a_auditoria_registra(ctx):
    d = novo(ctx)
    resp = ctx.client.get(f"/api/diarios/{d['id']}", headers=DONO_DE_B)
    assert resp.status_code == 404 and resp.json()["type"] == "https://nivelo/erros/nao-encontrado"
    assert ctx.eventos[-1]["acao"] == "recurso.nao_encontrado_outro_tenant"
    assert ctx.eventos[-1]["recurso"] == f"diario:{d['id']}" and ctx.eventos[-1]["usuario_id"] == DONO_B
    assert ctx.client.get(f"/api/obras/{OBRA_A1}/diarios", headers=DONO_DE_B).status_code == 404

    inexistente = str(uuid.uuid4())
    antes = len(ctx.eventos)
    assert ctx.client.get(f"/api/diarios/{inexistente}", headers=DONO_DE_B).status_code == 404
    assert len(ctx.eventos) == antes  # não existe em lugar nenhum: sem evento de tenancy


@pytest.mark.parametrize(
    "metodo, rota, corpo",
    [
        ("put", "/api/diarios/{d}", {**DIARIO, "versao": 1}),
        ("post", "/api/diarios/{d}/publicar", None),
        ("delete", "/api/diarios/{d}", None),
        ("post", "/api/diarios/{d}/fotos/upload-url", {"content_type": "image/jpeg", "tamanho_bytes": 1000}),
        ("get", "/api/diarios/{d}/revisoes", None),
        ("get", "/api/diarios/{d}/comentarios", None),
        ("post", "/api/diarios/{d}/comentarios", {"texto": "oi"}),
    ],
)
def test_b_nao_le_nem_altera_nada_do_diario_de_a(ctx, metodo, rota, corpo):
    d = novo(ctx)
    kw = {} if corpo is None else {"json": corpo}
    assert getattr(ctx.client, metodo)(rota.format(d=d["id"]), headers=DONO_DE_B, **kw).status_code == 404
    assert ctx.client.get(f"/api/diarios/{d['id']}", headers=DONO).json()["versao"] == 1


def test_b_nao_registra_diario_na_obra_de_a_nem_a_na_de_b(ctx):
    assert registrar(ctx, OBRA_A1, DONO_DE_B).status_code == 404
    assert registrar(ctx, OBRA_B1, DONO).status_code == 404


def test_listagem_pagina_com_total_e_filtra_por_status(ctx):
    for dia in ("2026-11-01", "2026-11-02", "2026-11-03"):
        novo(ctx, data=dia)
    publicar(ctx, ctx.client.get(f"/api/obras/{OBRA_A1}/diarios", headers=ENC).json()["itens"][0])
    pagina = ctx.client.get(f"/api/obras/{OBRA_A1}/diarios?por_pagina=2", headers=ENC).json()
    assert (pagina["total"], pagina["pagina"], pagina["por_pagina"]) == (3, 1, 2)
    assert [d["data"] for d in pagina["itens"]] == ["2026-11-03", "2026-11-02"]
    assert pagina["itens"][0]["ocorrencias"] == 1 and pagina["itens"][0]["fotos"] == 0
    publicados = ctx.client.get(f"/api/obras/{OBRA_A1}/diarios?status=publicado", headers=ENC).json()
    assert publicados["total"] == 1 and publicados["itens"][0]["data"] == "2026-11-03"


# ── Edição, versão e publicação ──────────────────────────────────────────────


def test_editar_rascunho_incrementa_a_versao_e_versao_velha_da_409(ctx):
    d = novo(ctx)
    resp = editar(ctx, d, efetivo=6)
    assert resp.status_code == 200 and resp.json()["versao"] == 2 and resp.json()["efetivo"] == 6
    resp = editar(ctx, d, versao=1, efetivo=7)
    assert resp.status_code == 409 and resp.json()["versao_atual"] == 2


def test_editar_sem_versao_e_428_e_if_match_vale(ctx):
    d = novo(ctx)
    corpo = {**DIARIO, "efetivo": 9}
    assert ctx.client.put(f"/api/diarios/{d['id']}", json=corpo, headers=ENC).status_code == 428
    resp = ctx.client.put(f"/api/diarios/{d['id']}", json=corpo, headers={**ENC, "If-Match": '"1"'})
    assert resp.status_code == 200 and resp.headers["ETag"] == '"2"'


def test_mudar_a_data_para_um_dia_que_ja_tem_diario_e_409(ctx):
    novo(ctx, data="2026-11-02")
    d = novo(ctx)
    assert editar(ctx, d, data="2026-11-02").status_code == 409


def test_publicar_exige_atividades_e_nao_publica_duas_vezes(ctx):
    d = novo(ctx, atividades="")
    resp = ctx.client.post(f"/api/diarios/{d['id']}/publicar", headers=ENC)
    assert resp.status_code == 422 and resp.json()["type"] == "https://nivelo/erros/diario-publicar-sem-atividades"
    d = editar(ctx, d, atividades="Alvenaria").json()
    pub = publicar(ctx, d)
    assert pub["status"] == "publicado" and pub["publicado_em"] and pub["versao"] == 3
    resp = ctx.client.post(f"/api/diarios/{d['id']}/publicar", headers=ENC)
    assert resp.status_code == 409 and resp.json()["type"] == "https://nivelo/erros/diario-ja-publicado"
    assert outbox(ctx)[-1]["tipo"] == "diario.publicado"


# ── Revisão do diário publicado ──────────────────────────────────────────────


def test_editar_publicado_sem_motivo_e_recusado(ctx):
    d = publicar(ctx, novo(ctx))
    resp = editar(ctx, d, efetivo=6)
    assert resp.status_code == 422 and resp.json()["type"] == "https://nivelo/erros/diario-revisao-sem-motivo"
    assert ctx.client.get(f"/api/diarios/{d['id']}", headers=DONO).json()["efetivo"] == 4


def test_revisao_guarda_o_retrato_anterior_e_todos_os_membros_veem(ctx):
    d = publicar(ctx, novo(ctx))
    resp = editar(ctx, d, efetivo=6, motivo="Faltou contar o ajudante")
    assert resp.status_code == 200, resp.text
    revisado = resp.json()
    assert revisado["efetivo"] == 6 and revisado["status"] == "publicado" and revisado["revisoes"] == 1
    assert revisado["versao"] == d["versao"] + 1

    [rev] = ctx.client.get(f"/api/diarios/{d['id']}/revisoes", headers=DONO).json()
    assert rev["motivo"] == "Faltou contar o ajudante" and rev["versao_anterior"] == d["versao"]
    assert rev["retrato"]["efetivo"] == 4 and rev["autor_id"] == ENC_A
    evento = outbox(ctx)[-1]
    assert evento["tipo"] == "diario.revisado" and evento["dados"]["motivo"] == "Faltou contar o ajudante"


def test_encarregado_so_revisa_os_proprios_e_o_403_e_auditado(ctx):
    d = publicar(ctx, novo(ctx))  # autor: ENC_A
    resp = editar(ctx, d, quem=OUTRO_ENC, efetivo=6, motivo="Corrigir efetivo")
    assert resp.status_code == 403 and resp.json()["type"] == "https://nivelo/erros/acesso-negado"
    assert ctx.eventos[-1]["acao"] == "acesso.negado" and ctx.eventos[-1]["usuario_id"] == MULTI
    assert editar(ctx, d, quem=DONO, efetivo=6, motivo="Corrigir efetivo").status_code == 200


def test_rascunho_de_outro_encarregado_da_obra_pode_ser_editado(ctx):
    d = novo(ctx)
    assert editar(ctx, d, quem=OUTRO_ENC, efetivo=5).status_code == 200


def test_revisao_sem_mudanca_e_422(ctx):
    d = publicar(ctx, novo(ctx))
    resp = editar(ctx, d, motivo="Só conferindo")
    assert resp.status_code == 422 and resp.json()["type"] == "https://nivelo/erros/diario-revisao-sem-mudanca"


# ── Remoção ──────────────────────────────────────────────────────────────────


def test_dono_remove_rascunho_com_as_fotos_e_nao_remove_publicado(ctx):
    d = novo(ctx)
    foto = anexar(ctx, d)
    assert ctx.client.delete(f"/api/diarios/{d['id']}", headers=DONO).status_code == 204
    assert ctx.client.get(f"/api/diarios/{d['id']}", headers=DONO).status_code == 404
    assert ctx.storage.apagados == [foto["object_key"]]
    assert outbox(ctx)[-1]["tipo"] == "diario.removido"

    pub = publicar(ctx, novo(ctx))
    resp = ctx.client.delete(f"/api/diarios/{pub['id']}", headers=DONO)
    assert resp.status_code == 409 and resp.json()["type"] == "https://nivelo/erros/diario-ja-publicado"


# ── Fotos ────────────────────────────────────────────────────────────────────


def pedir_upload(ctx, diario, quem=ENC, content_type="image/jpeg", tamanho=300_000):
    return ctx.client.post(
        f"/api/diarios/{diario['id']}/fotos/upload-url",
        json={"content_type": content_type, "tamanho_bytes": tamanho},
        headers=quem,
    )


def anexar(ctx, diario, quem=ENC, tamanho=300_000, legenda="Contrapiso"):
    pedido = pedir_upload(ctx, diario, quem).json()
    ctx.storage.objetos[pedido["object_key"]] = (tamanho, "image/jpeg")  # o PUT do navegador
    resp = ctx.client.post(
        f"/api/diarios/{diario['id']}/fotos",
        json={"object_key": pedido["object_key"], "legenda": legenda},
        headers=quem,
    )
    assert resp.status_code == 201, resp.text
    return {**resp.json(), "object_key": pedido["object_key"]}


def test_upload_url_devolve_a_chave_no_formato_e_a_url_de_put(ctx):
    d = novo(ctx)
    resp = pedir_upload(ctx, d, content_type="image/webp")
    assert resp.status_code == 200, resp.text
    p = resp.json()
    assert p["object_key"] == f"empresas/{EMPRESA_A}/obras/{OBRA_A1}/diarios/{d['id']}/{p['foto_id']}.webp"
    assert p["url"].startswith(f"/storage/bucket/{p['object_key']}?") and "X-Amz-Expires=300" in p["url"]
    assert p["metodo"] == "PUT" and p["headers"] == {"Content-Type": "image/webp"} and p["expira_em_segundos"] == 300


def test_upload_url_recusa_tipo_e_tamanho_fora_do_permitido(ctx):
    d = novo(ctx)
    assert pedir_upload(ctx, d, content_type="image/gif").status_code == 422
    assert pedir_upload(ctx, d, tamanho=5 * 1024 * 1024 + 1).status_code == 422


def test_confirmar_grava_a_foto_e_e_idempotente(ctx):
    d = novo(ctx)
    foto = anexar(ctx, d)
    assert foto["tamanho_bytes"] == 300_000 and foto["legenda"] == "Contrapiso" and foto["enviado_por"] == ENC_A
    de_novo = ctx.client.post(
        f"/api/diarios/{d['id']}/fotos", json={"object_key": foto["object_key"]}, headers=ENC
    ).json()
    assert de_novo["id"] == foto["id"]
    detalhe = ctx.client.get(f"/api/diarios/{d['id']}", headers=ENC).json()
    assert [f["id"] for f in detalhe["fotos"]] == [foto["id"]] and detalhe["versao"] == 1  # foto não muda a versão
    evento = outbox(ctx)[-1]
    assert evento["tipo"] == "foto.anexada" and evento["recurso_id"] == foto["id"]
    assert evento["dados"]["object_key"] == foto["object_key"]


def test_confirmar_sem_o_objeto_no_bucket_e_422(ctx):
    d = novo(ctx)
    chave = pedir_upload(ctx, d).json()["object_key"]
    resp = ctx.client.post(f"/api/diarios/{d['id']}/fotos", json={"object_key": chave}, headers=ENC)
    assert resp.status_code == 422 and resp.json()["type"] == "https://nivelo/erros/foto-invalida"


def test_objeto_maior_que_5_mb_ou_de_outro_tipo_e_recusado_e_apagado(ctx):
    d = novo(ctx)
    for tamanho, tipo in ((6 * 1024 * 1024, "image/jpeg"), (1000, "image/gif")):
        chave = pedir_upload(ctx, d).json()["object_key"]
        ctx.storage.objetos[chave] = (tamanho, tipo)
        resp = ctx.client.post(f"/api/diarios/{d['id']}/fotos", json={"object_key": chave}, headers=ENC)
        assert resp.status_code == 422 and chave in ctx.storage.apagados and chave not in ctx.storage.objetos


def test_chave_de_outro_diario_ou_de_outra_empresa_nao_e_anexada(ctx):
    d, outro = novo(ctx), novo(ctx, data="2026-11-02")
    chave = pedir_upload(ctx, outro).json()["object_key"]
    ctx.storage.objetos[chave] = (1000, "image/jpeg")
    resp = ctx.client.post(f"/api/diarios/{d['id']}/fotos", json={"object_key": chave}, headers=ENC)
    assert resp.status_code == 422
    alheia = chave.replace(EMPRESA_A, EMPRESA_B)
    assert (
        ctx.client.post(f"/api/diarios/{outro['id']}/fotos", json={"object_key": alheia}, headers=ENC).status_code
        == 422
    )
    malformada = {"object_key": "../../etc/passwd"}
    assert ctx.client.post(f"/api/diarios/{d['id']}/fotos", json=malformada, headers=ENC).status_code == 422


def test_url_da_foto_para_quem_ve_o_diario(ctx):
    d = novo(ctx, OBRA_A2, DONO)
    foto = anexar(ctx, d, DONO)
    resp = ctx.client.get(f"/api/fotos/{foto['id']}/url", headers=DONO)
    assert resp.status_code == 200 and resp.json()["expira_em_segundos"] == 600
    assert foto["object_key"] in resp.json()["url"]
    assert ctx.client.get(f"/api/fotos/{foto['id']}/url", headers=CLI).status_code == 404  # rascunho
    publicar(ctx, d, DONO)
    assert ctx.client.get(f"/api/fotos/{foto['id']}/url", headers=CLI).status_code == 200
    assert ctx.client.get(f"/api/fotos/{foto['id']}/url", headers=ENC).status_code == 404  # não é membro de A2
    assert ctx.client.get(f"/api/fotos/{foto['id']}/url", headers=DONO_DE_B).status_code == 404
    assert ctx.eventos[-1]["acao"] == "recurso.nao_encontrado_outro_tenant"
    assert ctx.eventos[-1]["recurso"] == f"foto:{foto['id']}"


def test_remover_foto_so_em_rascunho_e_apaga_o_objeto(ctx):
    d = novo(ctx)
    foto = anexar(ctx, d)
    assert ctx.client.delete(f"/api/fotos/{foto['id']}", headers=DONO_DE_B).status_code == 404
    assert ctx.client.delete(f"/api/fotos/{foto['id']}", headers=CLI).status_code == 403
    assert ctx.client.delete(f"/api/fotos/{foto['id']}", headers=ENC).status_code == 204
    assert ctx.storage.apagados == [foto["object_key"]] and outbox(ctx)[-1]["tipo"] == "foto.removida"
    assert ctx.client.delete(f"/api/fotos/{foto['id']}", headers=ENC).status_code == 404

    pub = publicar(ctx, novo(ctx, data="2026-11-02"))
    foto = anexar(ctx, pub)  # publicado aceita foto nova
    resp = ctx.client.delete(f"/api/fotos/{foto['id']}", headers=ENC)
    assert resp.status_code == 409 and foto["object_key"] not in ctx.storage.apagados


def _encher_de_fotos(ctx, diario, n):
    from app.obras.infrastructure.modelos import DiarioFotoModel
    from app.shared.infrastructure.tenancy import definir_tenant

    with ctx.SessionLocal() as s:
        definir_tenant(s, uuid.UUID(EMPRESA_A))
        for _ in range(n):
            fid = uuid.uuid4()
            s.add(
                DiarioFotoModel(
                    id=fid,
                    empresa_id=uuid.UUID(EMPRESA_A),
                    diario_id=uuid.UUID(diario["id"]),
                    object_key=f"empresas/{EMPRESA_A}/obras/{OBRA_A1}/diarios/{diario['id']}/{fid}.jpg",
                    content_type="image/jpeg",
                    tamanho_bytes=1000,
                    enviado_por=ENC_A,
                    criado_em=datetime(2026, 11, 3, 12, 0),
                )
            )
        s.commit()


def test_free_permite_30_fotos_por_obra_e_a_31a_recebe_402(ctx):
    d = novo(ctx)
    _encher_de_fotos(ctx, d, 29)
    anexar(ctx, d)  # a 30ª
    outro_dia = novo(ctx, data="2026-11-02")  # o limite é por obra, não por diário
    resp = pedir_upload(ctx, outro_dia)
    assert resp.status_code == 402
    corpo = resp.json()
    assert corpo["type"] == "https://nivelo/erros/plano-limite-excedido"
    assert (corpo["limite"], corpo["atual"], corpo["plano_atual"], corpo["plano_sugerido"]) == (30, 30, "free", "pro")
    assert pedir_upload(ctx, novo(ctx, OBRA_A2, DONO), DONO).status_code == 200  # outra obra tem vaga


def test_confirmacao_tambem_confere_o_plano_e_apaga_o_objeto_recusado(ctx):
    d = novo(ctx)
    _encher_de_fotos(ctx, d, 29)
    chave = pedir_upload(ctx, d).json()["object_key"]  # ainda cabia
    anexar(ctx, d)  # outra foto ocupa a última vaga
    ctx.storage.objetos[chave] = (1000, "image/jpeg")
    resp = ctx.client.post(f"/api/diarios/{d['id']}/fotos", json={"object_key": chave}, headers=ENC)
    assert resp.status_code == 402 and chave in ctx.storage.apagados


def test_pro_nao_tem_limite_de_fotos(ctx):
    from test_obras_crud_api import plano

    plano(ctx, EMPRESA_A, "pro")
    d = novo(ctx)
    _encher_de_fotos(ctx, d, 30)
    assert pedir_upload(ctx, d).status_code == 200


# ── Comentários ──────────────────────────────────────────────────────────────


def test_comentario_so_em_publicado_e_qualquer_membro_comenta(ctx):
    d = novo(ctx, OBRA_A2, DONO)
    resp = ctx.client.post(f"/api/diarios/{d['id']}/comentarios", json={"texto": "Cedo demais"}, headers=DONO)
    assert resp.status_code == 409 and resp.json()["type"] == "https://nivelo/erros/diario-nao-publicado"
    publicar(ctx, d, DONO)
    resp = ctx.client.post(f"/api/diarios/{d['id']}/comentarios", json={"texto": " Pode seguir. "}, headers=CLI)
    assert resp.status_code == 201 and resp.json()["texto"] == "Pode seguir." and resp.json()["autor_id"] == CLI_A
    ctx.client.post(f"/api/diarios/{d['id']}/comentarios", json={"texto": "Combinado"}, headers=DONO)
    pagina = ctx.client.get(f"/api/diarios/{d['id']}/comentarios", headers=CLI).json()
    assert pagina["total"] == 2 and [c["texto"] for c in pagina["itens"]] == ["Pode seguir.", "Combinado"]
    assert outbox(ctx)[-1]["tipo"] == "comentario.registrado"
    assert ctx.client.get(f"/api/diarios/{d['id']}", headers=CLI).json()["versao"] == d["versao"] + 1  # só publicar


def test_comentario_vazio_e_422_e_quem_nao_ve_o_diario_recebe_404(ctx):
    d = publicar(ctx, novo(ctx, OBRA_A2, DONO), DONO)
    assert ctx.client.post(f"/api/diarios/{d['id']}/comentarios", json={"texto": ""}, headers=CLI).status_code == 422
    assert ctx.client.post(f"/api/diarios/{d['id']}/comentarios", json={"texto": "oi"}, headers=ENC).status_code == 404


# ── Histórico da obra ────────────────────────────────────────────────────────


def test_historico_da_obra_so_para_o_dono_e_presa_a_empresa_do_token(ctx):
    resp = ctx.client.get(f"/api/obras/{OBRA_A1}/historico?limite=10", headers=DONO)
    assert resp.status_code == 200 and resp.json()[0]["tipo"] == "obra.criada"
    assert ctx.historico.pedidos == [(EMPRESA_A, OBRA_A1, 10)]
    assert ctx.client.get(f"/api/obras/{OBRA_A1}/historico", headers=ENC).status_code == 403
    assert ctx.client.get(f"/api/obras/{OBRA_A1}/historico", headers=DONO_DE_B).status_code == 404
    assert len(ctx.historico.pedidos) == 1  # o 404 vem antes de consultar a auditoria


def test_historico_consulta_o_log_service_com_a_empresa_do_token_e_descarta_o_resto(ctx, monkeypatch):
    import json

    import httpx

    from app.obras.domain.ids import ObraId
    from app.obras.infrastructure.historico import HistoricoViaLogService
    from app.shared.application.contexto import TenantContext
    from app.shared.application.erros import DependenciaIndisponivel
    from app.shared.domain.ids import EmpresaId

    pedidos = []

    def fake_get(url, params=None, headers=None, timeout=None):
        pedidos.append(params)
        do_stream = {
            "event_id": "e1",
            "tipo": "diario.publicado",
            "usuario_id": "2",
            "empresa_id": EMPRESA_A,
            "recurso": "diario:d1",
            "recurso_id": "d1",
            "timestamp": "2026-11-04T14:02:11.000Z",
            "dados": json.dumps({"obra_id": OBRA_A1}),
        }
        corpo = [do_stream, {"event_id": "e2", "tipo": "obra.criada", "empresa_id": EMPRESA_B}]
        return httpx.Response(200, json=corpo, request=httpx.Request("GET", url))

    monkeypatch.setattr("app.obras.infrastructure.historico.httpx.get", fake_get)
    c = TenantContext(empresa_id=EmpresaId(uuid.UUID(EMPRESA_A)), usuario_id=DONO_A, papel="dono")
    [evento] = HistoricoViaLogService().eventos(c, ObraId(uuid.UUID(OBRA_A1)), 50)
    assert pedidos == [{"empresa_id": EMPRESA_A, "obra_id": OBRA_A1, "limit": 50}]
    assert (evento["tipo"], evento["ator_id"], evento["recurso"]) == ("diario.publicado", 2, "diario")
    assert evento["ocorrido_em"] == "2026-11-04T14:02:11.000Z" and evento["dados"] == {"obra_id": OBRA_A1}

    def fora(url, **kw):
        raise httpx.ConnectError("sem rota")

    monkeypatch.setattr("app.obras.infrastructure.historico.httpx.get", fora)
    with pytest.raises(DependenciaIndisponivel):
        HistoricoViaLogService().eventos(c, ObraId(uuid.UUID(OBRA_A1)), 50)
