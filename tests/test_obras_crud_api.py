"""Fase 4a: CRUD de obras e membros pela API, com JWT de verdade e SQLite.

Dados (tests/conftest.py): empresa A com 2 obras ativas (A1 com o encarregado ENC_A e MULTI,
A2 com o cliente CLI_A) e uma removida; empresa B com B1. A empresa C começa vazia, no Free.
"""

import uuid

import pytest
from conftest import CLI_A, DONO_A, DONO_B, EMPRESA_A, EMPRESA_B, ENC_A, OBRA_A1, OBRA_A2
from test_obras_api import tk

# Tenancy, papéis e plano: rodam também no MariaDB (tests/banco_de_teste.py)
pytestmark = pytest.mark.mariadb

EMPRESA_C = "0190f3a0-0000-7000-8000-00000000000c"
DONO_C, ENC_C, CLI_C = 21, 22, 23

OBRA = {
    "nome": "Casa do Jorge",
    "endereco": {"logradouro": "Rua das Acácias, 120", "cidade": "Marília", "uf": "sp"},
    "cliente_nome": "Jorge Alves",
    "data_inicio": "2026-11-03",
    "previsao_termino": "2027-03-31",
}

DONO = {"A": tk(DONO_A, EMPRESA_A, "dono"), "B": tk(DONO_B, EMPRESA_B, "dono"), "C": tk(DONO_C, EMPRESA_C, "dono")}


class EquipeFalsa:
    papeis = {ENC_A: "encarregado", CLI_A: "cliente", ENC_C: "encarregado", CLI_C: "cliente"}

    def __init__(self):
        self.consultas = 0

    def papel_de(self, usuario_id):
        self.consultas += 1
        return self.papeis.get(usuario_id.valor)


@pytest.fixture
def ctx(obras_ctx):
    from app.main import app
    from app.obras.api import rotas

    equipe = EquipeFalsa()
    app.dependency_overrides[rotas.equipe_da_empresa] = lambda: equipe
    obras_ctx.equipe = equipe
    yield obras_ctx
    app.dependency_overrides.pop(rotas.equipe_da_empresa, None)


def plano(ctx, empresa, plano_, status="active"):
    from app.assinaturas.infrastructure.modelos import AssinaturaModel
    from app.shared.infrastructure.tenancy import sem_tenant

    db = ctx.SessionLocal()
    with sem_tenant(db, "teste: muda o plano"):
        db.merge(AssinaturaModel(empresa_id=uuid.UUID(empresa), plano=plano_, status=status))
        db.commit()
    db.close()


def criar(ctx, empresa="C", **extras):
    return ctx.client.post("/api/obras", json={**OBRA, **extras}, headers=DONO[empresa])


def acoes_de_escrita(obra_id):
    return [
        ("put", f"/api/obras/{obra_id}", {**OBRA, "versao": 1}),
        ("patch", f"/api/obras/{obra_id}/status", {"status": "pausada"}),
        ("delete", f"/api/obras/{obra_id}", None),
        ("post", f"/api/obras/{obra_id}/membros", {"usuario_id": ENC_A, "papel": "encarregado"}),
        ("delete", f"/api/obras/{obra_id}/membros/{ENC_A}", None),
    ]


def chamar(ctx, metodo, rota, corpo, headers):
    if corpo is None:
        return ctx.client.request(metodo.upper(), rota, headers=headers)
    return ctx.client.request(metodo.upper(), rota, json=corpo, headers=headers)


# ── Criar e o limite do plano ────────────────────────────────────────────────


def test_dono_cria_obra_ativa_com_versao_e_location(ctx):
    resp = criar(ctx)
    assert resp.status_code == 201, resp.text
    corpo = resp.json()
    assert corpo["status"] == "ativa" and corpo["versao"] == 1 and corpo["membros"] == []
    assert corpo["endereco"]["uf"] == "SP"
    assert resp.headers["ETag"] == '"1"'
    assert resp.headers["Location"] == f"/api/obras/{corpo['id']}"
    assert uuid.UUID(corpo["id"]).version == 7
    assert ctx.client.get(resp.headers["Location"], headers=DONO["C"]).json()["nome"] == "Casa do Jorge"


def test_free_recusa_a_segunda_obra_ativa_com_402_e_problem_details(ctx):
    assert criar(ctx).status_code == 201
    resp = criar(ctx, nome="Segunda obra")
    assert resp.status_code == 402
    assert resp.headers["content-type"].startswith("application/problem+json")
    corpo = resp.json()
    assert corpo["type"] == "https://nivelo/erros/plano-limite-excedido"
    assert corpo["title"] == "Limite do plano Free atingido"
    assert corpo["detail"] == (
        "O plano Free permite 1 obra ativa e você já tem 1. "
        "Conclua ou pause uma obra, ou assine o Pro para ter obras ilimitadas."
    )
    assert {k: corpo[k] for k in ("limite", "atual", "plano_atual", "plano_sugerido", "acao")} == {
        "limite": 1,
        "atual": 1,
        "plano_atual": "free",
        "plano_sugerido": "pro",
        "acao": "/assinatura",
    }
    assert ctx.client.get("/api/obras", headers=DONO["C"]).json()["total"] == 1


def test_pro_cria_varias_e_pro_inadimplente_volta_ao_limite_do_free(ctx):
    plano(ctx, EMPRESA_C, "pro")
    assert [criar(ctx, nome=f"Obra {i}").status_code for i in range(3)] == [201, 201, 201]
    plano(ctx, EMPRESA_C, "pro", status="past_due")
    assert criar(ctx, nome="Quarta").status_code == 402


def test_empresa_nasce_free_na_primeira_checagem_do_plano(ctx):
    from app.assinaturas.infrastructure.modelos import AssinaturaModel
    from app.shared.infrastructure.tenancy import definir_tenant

    criar(ctx)
    db = ctx.SessionLocal()
    definir_tenant(db, uuid.UUID(EMPRESA_C))
    assert db.get(AssinaturaModel, uuid.UUID(EMPRESA_C)).plano == "free"
    db.close()


def test_empresa_id_no_corpo_e_ignorado(ctx):
    resp = criar(ctx, empresa_id=EMPRESA_B)
    assert resp.status_code == 201
    obra_id = resp.json()["id"]
    assert ctx.client.get(f"/api/obras/{obra_id}", headers=DONO["B"]).status_code == 404
    assert ctx.client.get(f"/api/obras/{obra_id}", headers=DONO["C"]).status_code == 200


@pytest.mark.parametrize(
    "mudanca, campo",
    [
        ({"previsao_termino": "2026-11-02"}, "obra-periodo-invalido"),
        ({"endereco": {**OBRA["endereco"], "uf": "XX"}}, "obra-dado-invalido"),
        ({"nome": "   "}, "obra-dado-invalido"),
    ],
)
def test_regras_da_obra_viram_422_com_type_proprio(ctx, mudanca, campo):
    resp = criar(ctx, **mudanca)
    assert resp.status_code == 422
    assert resp.json()["type"] == f"https://nivelo/erros/{campo}"


# ── Leitura ──────────────────────────────────────────────────────────────────


def test_listagem_pagina_e_filtra_por_status(ctx):
    plano(ctx, EMPRESA_C, "pro")
    ids = [criar(ctx, nome=f"Obra {i}").json()["id"] for i in range(3)]
    ctx.client.patch(f"/api/obras/{ids[0]}/status", json={"status": "pausada"}, headers=DONO["C"])

    pagina = ctx.client.get("/api/obras?page=1&por_pagina=2", headers=DONO["C"]).json()
    assert (pagina["total"], pagina["pagina"], pagina["por_pagina"], len(pagina["itens"])) == (3, 1, 2, 2)
    assert len(ctx.client.get("/api/obras?page=2&por_pagina=2", headers=DONO["C"]).json()["itens"]) == 1
    pausadas = ctx.client.get("/api/obras?status=pausada", headers=DONO["C"]).json()
    assert [o["id"] for o in pausadas["itens"]] == [ids[0]]
    assert ctx.client.get("/api/obras?status=demolida", headers=DONO["C"]).status_code == 422


def test_detalhe_para_membros_e_dono_com_lista_de_membros_so_para_o_dono(ctx):
    dono = ctx.client.get(f"/api/obras/{OBRA_A1}", headers=DONO["A"]).json()
    assert sorted(m["usuario_id"] for m in dono["membros"]) == [ENC_A, 5]

    enc = ctx.client.get(f"/api/obras/{OBRA_A1}", headers=tk(ENC_A, EMPRESA_A, "encarregado"))
    assert enc.status_code == 200 and enc.json()["membros"] is None
    # Encarregado fora da obra e cliente de outra obra: 404
    assert ctx.client.get(f"/api/obras/{OBRA_A2}", headers=tk(ENC_A, EMPRESA_A, "encarregado")).status_code == 404
    assert ctx.client.get(f"/api/obras/{OBRA_A1}", headers=tk(CLI_A, EMPRESA_A, "cliente")).status_code == 404
    assert ctx.client.get(f"/api/obras/{OBRA_A2}", headers=tk(CLI_A, EMPRESA_A, "cliente")).status_code == 200


# ── Tenancy (404) ────────────────────────────────────────────────────────────


def test_b_abrindo_a_obra_de_a_recebe_404_e_a_auditoria_registra(ctx):
    resp = ctx.client.get(f"/api/obras/{OBRA_A1}", headers=DONO["B"])
    assert resp.status_code == 404
    assert resp.json()["type"] == "https://nivelo/erros/nao-encontrado"
    assert ctx.eventos[-1] == {
        "acao": "recurso.nao_encontrado_outro_tenant",
        "usuario_id": DONO_B,
        "recurso": f"obra:{OBRA_A1}",
        "detalhes": f"GET /api/obras/{OBRA_A1}",
    }


def test_obra_inexistente_responde_igual_mas_sem_evento_de_tenancy(ctx):
    inexistente = "0190f3a0-0000-7000-8000-0000000000ff"
    de_outra = ctx.client.get(f"/api/obras/{OBRA_A1}", headers=DONO["B"]).json()
    nenhuma = ctx.client.get(f"/api/obras/{inexistente}", headers=DONO["B"]).json()
    assert {k: v for k, v in de_outra.items() if k not in ("instance", "request_id")} == {
        k: v for k, v in nenhuma.items() if k not in ("instance", "request_id")
    }
    assert ctx.eventos[-1]["recurso"] == f"obra:{OBRA_A1}"  # o 404 da inexistente não gerou evento


@pytest.mark.parametrize("acao", range(5))
def test_b_nao_altera_nada_da_obra_de_a(ctx, acao):
    metodo, rota, corpo = acoes_de_escrita(OBRA_A1)[acao]
    resp = chamar(ctx, metodo, rota, corpo, DONO["B"])
    assert resp.status_code == 404, resp.text
    assert ctx.eventos[-1]["acao"] == "recurso.nao_encontrado_outro_tenant"
    obra = ctx.client.get(f"/api/obras/{OBRA_A1}", headers=DONO["A"]).json()
    assert obra["versao"] == 1 and obra["status"] == "ativa" and len(obra["membros"]) == 2


# ── Papéis (403) ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("acao", range(5))
@pytest.mark.parametrize("quem", [(ENC_A, "encarregado"), (CLI_A, "cliente")])
def test_encarregado_e_cliente_nao_escrevem_em_obras(ctx, acao, quem):
    metodo, rota, corpo = acoes_de_escrita(OBRA_A1)[acao]
    resp = chamar(ctx, metodo, rota, corpo, tk(quem[0], EMPRESA_A, quem[1]))
    assert resp.status_code == 403
    assert ctx.eventos[-1]["acao"] == "acesso.negado" and ctx.eventos[-1]["usuario_id"] == quem[0]


def test_token_sem_empresa_nao_cria_nem_le_obra(ctx):
    from test_autenticacao_api import auth, token

    sem = auth(token("9", empresa_id=None, papel=None))
    assert ctx.client.post("/api/obras", json=OBRA, headers=sem).status_code == 403
    assert ctx.client.get(f"/api/obras/{OBRA_A1}", headers=sem).status_code == 403


# ── Editar com versão (409, 428) ─────────────────────────────────────────────


def test_editar_com_if_match_incrementa_a_versao_e_versao_velha_da_409(ctx):
    obra = criar(ctx).json()
    url = f"/api/obras/{obra['id']}"
    resp = ctx.client.put(url, json={**OBRA, "nome": "Nome novo"}, headers={**DONO["C"], "If-Match": '"1"'})
    assert resp.status_code == 200, resp.text
    assert resp.json()["versao"] == 2 and resp.headers["ETag"] == '"2"' and resp.json()["nome"] == "Nome novo"

    velha = ctx.client.put(url, json={**OBRA, "nome": "Atropelo"}, headers={**DONO["C"], "If-Match": '"1"'})
    assert velha.status_code == 409
    assert velha.json()["type"] == "https://nivelo/erros/conflito-de-versao" and velha.json()["versao_atual"] == 2
    assert ctx.client.get(url, headers=DONO["C"]).json()["nome"] == "Nome novo"

    # A versão também pode ir no corpo
    assert ctx.client.put(url, json={**OBRA, "versao": 2}, headers=DONO["C"]).json()["versao"] == 3


def test_editar_sem_versao_e_428_e_versoes_divergentes_400(ctx):
    obra = criar(ctx).json()
    url = f"/api/obras/{obra['id']}"
    sem = ctx.client.put(url, json=OBRA, headers=DONO["C"])
    assert sem.status_code == 428 and sem.json()["type"] == "https://nivelo/erros/precondicao-obrigatoria"
    divergente = ctx.client.put(url, json={**OBRA, "versao": 2}, headers={**DONO["C"], "If-Match": '"1"'})
    assert divergente.status_code == 400
    assert ctx.client.put(url, json=OBRA, headers={**DONO["C"], "If-Match": "abc"}).status_code == 400


def test_editar_sem_mudanca_nao_muda_a_versao(ctx):
    obra = criar(ctx).json()
    resp = ctx.client.put(f"/api/obras/{obra['id']}", json={**OBRA, "versao": 1}, headers=DONO["C"])
    assert resp.status_code == 200 and resp.json()["versao"] == 1


def test_update_concorrente_no_repositorio_vira_conflito(ctx):
    """Duas transações leem a versão 1; a segunda a gravar recebe ConflitoDeVersao (WHERE versao)."""
    from app.assinaturas.infrastructure.direitos import ConsultaDireitosSQL
    from app.obras.domain.ids import ObraId
    from app.obras.infrastructure.unidade_de_trabalho import UnidadeDeTrabalhoDeObrasSQL
    from app.shared.domain.erros import ConflitoDeVersao
    from app.shared.domain.ids import EmpresaId, UsuarioId
    from app.shared.infrastructure.tenancy import definir_tenant

    # Pela unidade de trabalho, como na produção: no MariaDB ela roda em READ COMMITTED (ADR 011)
    empresa = EmpresaId(uuid.UUID(EMPRESA_A))
    sessoes = [ctx.SessionLocal(), ctx.SessionLocal()]
    uows = []
    for s in sessoes:
        definir_tenant(s, empresa.valor)
        uows.append(UnidadeDeTrabalhoDeObrasSQL(s, empresa, ConsultaDireitosSQL(s)).__enter__())
    obras = [u.obras for u in uows]
    primeira, segunda = (repo.obter(ObraId(uuid.UUID(OBRA_A1))) for repo in obras)
    for obra, nome in ((primeira, "Primeira"), (segunda, "Segunda")):
        obra.editar(
            nome=nome,
            endereco=obra.endereco,
            cliente_nome=obra.cliente_nome,
            periodo=obra.periodo,
            ator=UsuarioId(DONO_A),
        )
    obras[0].salvar(primeira)
    sessoes[0].commit()
    with pytest.raises(ConflitoDeVersao):
        obras[1].salvar(segunda)
    for s in sessoes:
        s.rollback()
        s.close()
    assert ctx.client.get(f"/api/obras/{OBRA_A1}", headers=DONO["A"]).json()["nome"] == "Primeira"


# ── Status e remoção ─────────────────────────────────────────────────────────


def test_pausar_reativar_concluir_e_concluida_e_final(ctx):
    url = f"/api/obras/{criar(ctx).json()['id']}/status"
    assert ctx.client.patch(url, json={"status": "pausada"}, headers=DONO["C"]).json()["status"] == "pausada"
    assert ctx.client.patch(url, json={"status": "ativa"}, headers=DONO["C"]).json()["status"] == "ativa"
    concluida = ctx.client.patch(url, json={"status": "concluida", "versao": 3}, headers=DONO["C"])
    assert concluida.status_code == 200 and concluida.json()["versao"] == 4
    resp = ctx.client.patch(url, json={"status": "ativa"}, headers=DONO["C"])
    assert resp.status_code == 422
    assert resp.json()["type"] == "https://nivelo/erros/obra-transicao-de-status-invalida"
    assert ctx.client.patch(url, json={"status": "pausada", "versao": 1}, headers=DONO["C"]).status_code == 409


def test_reativar_obra_pausada_passa_pelo_plano(ctx):
    primeira = criar(ctx).json()["id"]
    ctx.client.patch(f"/api/obras/{primeira}/status", json={"status": "pausada"}, headers=DONO["C"])
    assert criar(ctx, nome="Segunda").status_code == 201  # pausada não ocupa vaga
    resp = ctx.client.patch(f"/api/obras/{primeira}/status", json={"status": "ativa"}, headers=DONO["C"])
    assert resp.status_code == 402 and resp.json()["atual"] == 1


def test_remover_e_soft_delete_some_da_listagem_e_libera_a_vaga(ctx):
    from app.obras.infrastructure.modelos import ObraModel
    from app.shared.infrastructure.tenancy import definir_tenant

    obra_id = criar(ctx).json()["id"]
    resp = ctx.client.delete(f"/api/obras/{obra_id}", headers={**DONO["C"], "If-Match": '"1"'})
    assert resp.status_code == 204
    assert ctx.client.get(f"/api/obras/{obra_id}", headers=DONO["C"]).status_code == 404
    assert ctx.client.delete(f"/api/obras/{obra_id}", headers=DONO["C"]).status_code == 404
    assert ctx.client.get("/api/obras", headers=DONO["C"]).json()["total"] == 0
    assert criar(ctx, nome="Nova").status_code == 201  # a removida não conta no limite

    db = ctx.SessionLocal()
    definir_tenant(db, uuid.UUID(EMPRESA_C))
    assert db.get(ObraModel, uuid.UUID(obra_id)).removida_em is not None  # a linha continua
    db.close()


# ── Membros ──────────────────────────────────────────────────────────────────


def test_dono_adiciona_e_remove_membro_e_o_acesso_acompanha(ctx):
    obra_id = criar(ctx).json()["id"]
    enc = tk(ENC_C, EMPRESA_C, "encarregado")
    assert ctx.client.get(f"/api/obras/{obra_id}", headers=enc).status_code == 404

    resp = ctx.client.post(
        f"/api/obras/{obra_id}/membros", json={"usuario_id": ENC_C, "papel": "encarregado"}, headers=DONO["C"]
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["usuario_id"] == ENC_C and resp.json()["papel"] == "encarregado"
    assert ctx.client.get(f"/api/obras/{obra_id}", headers=enc).status_code == 200
    detalhe = ctx.client.get(f"/api/obras/{obra_id}", headers=DONO["C"]).json()
    assert [m["usuario_id"] for m in detalhe["membros"]] == [ENC_C]
    assert detalhe["versao"] == 1  # membros não disputam a versão dos dados da obra

    repetido = ctx.client.post(
        f"/api/obras/{obra_id}/membros", json={"usuario_id": ENC_C, "papel": "encarregado"}, headers=DONO["C"]
    )
    assert repetido.status_code == 409

    assert ctx.client.delete(f"/api/obras/{obra_id}/membros/{ENC_C}", headers=DONO["C"]).status_code == 204
    assert ctx.client.get(f"/api/obras/{obra_id}", headers=enc).status_code == 404
    assert ctx.client.delete(f"/api/obras/{obra_id}/membros/{ENC_C}", headers=DONO["C"]).status_code == 404


@pytest.mark.parametrize(
    "usuario, papel, trecho",
    [(999, "encarregado", "não faz parte da empresa"), (CLI_C, "encarregado", "está na empresa como cliente")],
)
def test_membro_precisa_ter_vinculo_com_o_mesmo_papel(ctx, usuario, papel, trecho):
    obra_id = criar(ctx).json()["id"]
    resp = ctx.client.post(
        f"/api/obras/{obra_id}/membros", json={"usuario_id": usuario, "papel": papel}, headers=DONO["C"]
    )
    assert resp.status_code == 422
    assert resp.json()["type"] == "https://nivelo/erros/obra-membro-invalido" and trecho in resp.json()["detail"]


def test_membro_com_papel_de_dono_e_recusado_na_validacao(ctx):
    obra_id = criar(ctx).json()["id"]
    resp = ctx.client.post(
        f"/api/obras/{obra_id}/membros", json={"usuario_id": DONO_C, "papel": "dono"}, headers=DONO["C"]
    )
    assert resp.status_code == 422 and ctx.equipe.consultas == 0


def test_auth_service_fora_do_ar_ao_conferir_a_equipe_e_503(ctx, monkeypatch):
    import httpx

    from app.main import app
    from app.obras.api import rotas

    app.dependency_overrides.pop(rotas.equipe_da_empresa)

    def falha(*a, **kw):
        raise httpx.ConnectError("fora do ar")

    monkeypatch.setattr("app.obras.infrastructure.equipe.httpx.get", falha)
    obra_id = criar(ctx).json()["id"]
    resp = ctx.client.post(
        f"/api/obras/{obra_id}/membros", json={"usuario_id": ENC_C, "papel": "encarregado"}, headers=DONO["C"]
    )
    assert resp.status_code == 503 and resp.json()["type"] == "https://nivelo/erros/servico-indisponivel"


def test_equipe_vem_do_auth_service_com_o_token_do_dono(ctx, monkeypatch):
    from app.main import app
    from app.obras.api import rotas

    app.dependency_overrides.pop(rotas.equipe_da_empresa)
    pedidos = []

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"usuario_id": ENC_C, "papel": "encarregado"}]

    def fake_get(url, headers=None, timeout=None):
        pedidos.append({"url": url, "headers": headers})
        return Resposta()

    monkeypatch.setattr("app.obras.infrastructure.equipe.httpx.get", fake_get)
    obra_id = criar(ctx).json()["id"]
    resp = ctx.client.post(
        f"/api/obras/{obra_id}/membros", json={"usuario_id": ENC_C, "papel": "encarregado"}, headers=DONO["C"]
    )
    assert resp.status_code == 201
    assert pedidos[0]["url"].endswith("/equipe")
    assert pedidos[0]["headers"]["authorization"] == DONO["C"]["Authorization"]
    assert "X-Request-ID" in pedidos[0]["headers"]
