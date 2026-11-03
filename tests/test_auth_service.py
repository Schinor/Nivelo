import os
import sys

# Define variáveis de ambiente para a suíte de testes
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_12345678901234567890"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "120"
os.environ["RESET_TOKEN_EXPIRE_MINUTES"] = "30"

# Adiciona caminhos
sys.path.insert(0, os.path.abspath("auth-service"))

from datetime import UTC, datetime, timedelta
from email import message_from_string

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rbac_seed import seed_rbac
from app.main import app
from app.models.reset_token import ResetToken
from app.models.usuario import Usuario
from app.repositories import usuario_repo

# Banco de dados em memória exclusivo para a suite de testes automatizados
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def emails_enviados(monkeypatch):
    """Substitui o envio SMTP e registra (to_email, token, user_name) de cada chamada."""
    enviados = []

    def fake_send(to_email, token, user_name="Usuário"):
        enviados.append({"to": to_email, "token": token, "nome": user_name})
        return True

    monkeypatch.setattr("app.routes.auth.send_password_reset_email", fake_send)
    return enviados


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()
    seed_rbac(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine_test)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["db"] == "up"
    assert data["service"] == "auth-service"


def test_cadastro_e_login_usuario():
    # 1. Cadastro
    cad_resp = client.post(
        "/cadastro",
        json={
            "nome": "Allan Schinor",
            "email": "allan@exemplo.com",
            "senha": "senhaSegura123",
            "empresa_nome": "Empresa Teste",
        },
    )
    assert cad_resp.status_code == 201
    cad_data = cad_resp.json()["usuario"]
    assert cad_resp.json()["papel"] == "dono"
    assert cad_resp.json()["empresa"]["nome"] == "Empresa Teste"
    assert cad_data["nome"] == "Allan Schinor"
    assert cad_data["email"] == "allan@exemplo.com"
    assert cad_data["role"] == "dono"
    assert cad_data["permissions"] == []
    user_id = cad_data["id"]

    # Cadastro duplicado deve falhar
    dup_resp = client.post(
        "/cadastro",
        json={
            "nome": "Allan 2",
            "email": "allan@exemplo.com",
            "senha": "senhaSegura123",
            "empresa_nome": "Empresa Teste",
        },
    )
    assert dup_resp.status_code == 409

    # 2. Login
    login_resp = client.post(
        "/login",
        data={"username": "allan@exemplo.com", "password": "senhaSegura123"},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    # 3. /me
    me_resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "allan@exemplo.com"
    assert me_resp.json()["permissions"] == []

    # 4. /users/{id}/role
    role_resp = client.get(f"/users/{user_id}/role")
    assert role_resp.status_code == 200
    assert role_resp.json()["role"] == "dono"


def test_matriz_de_papeis_do_nivelo():
    from app.core.rbac_seed import PAPEIS_DEFINICAO

    slugs = {r["slug"] for r in client.get("/roles").json()}
    assert slugs == {"admin", "dono", "encarregado", "cliente"}
    assert slugs == {p["slug"] for p in PAPEIS_DEFINICAO}

    # Os papéis de negócio ainda não têm permissões granulares (a autorização deles vem na Fase 3)
    papeis = {r["slug"]: r for r in client.get("/roles").json()}
    for slug in ("dono", "encarregado", "cliente"):
        assert papeis[slug]["permissoes"] == []
    admin_perms = {f"{p['action']}:{p['resource']}" for p in papeis["admin"]["permissoes"]}
    assert "administrar:sistema" in admin_perms and "visualizar:logs" in admin_perms


def test_seed_converte_papeis_antigos_e_remove_os_que_sairam_da_matriz():
    from app.core.rbac_seed import seed_rbac
    from app.models.papel import Papel
    from app.models.permissao import Permissao
    from app.models.usuario import Usuario

    db = TestingSessionLocal()
    antigo = Papel(name="Papel antigo", slug="papel-antigo", description="fora da matriz")
    perm_antiga = Permissao(action="ver", resource="coisa-antiga", description="fora da matriz")
    antigo.permissoes = [perm_antiga]
    db.add_all([antigo, perm_antiga])
    db.flush()
    usuario = usuario_repo.create(db, nome="Legado", email="legado@exemplo.com", senha="password123")
    usuario.role, usuario.role_id = "papel-antigo", antigo.id
    db.commit()

    seed_rbac(db)

    assert db.query(Papel).filter_by(slug="papel-antigo").count() == 0
    assert db.query(Permissao).filter_by(resource="coisa-antiga").count() == 0
    convertido = db.get(Usuario, usuario.id)
    assert convertido.role == "cliente" and convertido.papel.slug == "cliente"
    db.close()


@pytest.mark.parametrize(
    "extras",
    [{"papel": "admin"}, {"role": "admin"}, {"role": "encarregado", "papel": "cliente"}],
)
def test_cadastro_publico_ignora_papel_do_corpo_e_cria_dono(extras):
    email = f"cadastro-{abs(hash(str(extras)))}@exemplo.com"
    response = client.post(
        "/cadastro",
        json={"nome": "Quem Tenta", "email": email, "senha": "password123", "empresa_nome": "Empresa Teste", **extras},
    )

    assert response.status_code == 201
    assert response.json()["papel"] == "dono"
    data = response.json()["usuario"]
    assert data["role"] == "dono" and data["admin"] is False
    assert "administrar:sistema" not in data["permissions"]


def test_permissao_exclusiva_admin():
    # 1. Usuário comum tentando acessar endpoint de admin status -> 403
    client.post(
        "/cadastro",
        json={
            "nome": "Comum",
            "email": "comum@exemplo.com",
            "senha": "password123",
            "empresa_nome": "Empresa Teste",
            "role": "dono",
        },
    )
    user_token = client.post(
        "/login",
        data={"username": "comum@exemplo.com", "password": "password123"},
    ).json()["access_token"]

    denied = client.get("/admin/status", headers={"Authorization": f"Bearer {user_token}"})
    assert denied.status_code == 403

    # 2. Admin acessando endpoint exclusivo -> 200
    # Administradores são provisionados internamente, nunca pelo cadastro público.
    db = TestingSessionLocal()
    usuario_repo.create(
        db,
        nome="Siriani Admin",
        email="admin@exemplo.com",
        senha="adminSecret123",
        role="admin",
    )
    db.close()
    admin_token = client.post(
        "/login",
        data={"username": "admin@exemplo.com", "password": "adminSecret123"},
    ).json()["access_token"]

    allowed = client.get("/admin/status", headers={"Authorization": f"Bearer {admin_token}"})
    assert allowed.status_code == 200
    assert allowed.json()["admin_access"] is True


def test_fluxo_completo_esqueci_senha_e_redefinicao(emails_enviados):
    # 1. Cria usuário
    client.post(
        "/cadastro",
        json={
            "nome": "Usuario Teste",
            "email": "recuperar@exemplo.com",
            "senha": "senhaAntiga123",
            "empresa_nome": "Empresa Teste",
        },
    )

    # 2. Solicita recuperação para e-mail não cadastrado: resposta neutra e nenhum e-mail enviado
    fake_resp = client.post("/forgot-password", json={"email": "inexistente@exemplo.com"})
    assert fake_resp.status_code == 200
    assert emails_enviados == []

    # 3. Solicita recuperação para e-mail cadastrado: o token vai só por e-mail, nunca na resposta
    forgot_resp = client.post("/forgot-password", json={"email": "recuperar@exemplo.com"})
    assert forgot_resp.status_code == 200
    assert "token" not in forgot_resp.json()
    assert forgot_resp.json() == fake_resp.json()
    assert len(emails_enviados) == 1
    assert emails_enviados[0]["to"] == "recuperar@exemplo.com"
    token = emails_enviados[0]["token"]
    assert token

    # 4. Valida token antes do uso
    val_resp = client.get(f"/validate-reset-token/{token}")
    assert val_resp.status_code == 200
    assert val_resp.json()["valid"] is True
    assert val_resp.json()["email"] == "recuperar@exemplo.com"

    # 5. Redefine a senha com sucesso
    reset_resp = client.post(
        "/reset-password",
        json={"token": token, "nova_senha": "novaSenhaSuperSegura456"},
    )
    assert reset_resp.status_code == 200
    assert "sucesso" in reset_resp.json()["message"].lower()

    # 6. Login com senha antiga deve falhar (401)
    fail_login = client.post(
        "/login",
        data={"username": "recuperar@exemplo.com", "password": "senhaAntiga123"},
    )
    assert fail_login.status_code == 401

    # 7. Login com nova senha deve suceder (200)
    ok_login = client.post(
        "/login",
        data={"username": "recuperar@exemplo.com", "password": "novaSenhaSuperSegura456"},
    )
    assert ok_login.status_code == 200


def test_negativo_reuso_de_token(emails_enviados):
    client.post(
        "/cadastro",
        json={
            "nome": "Reuso Teste",
            "email": "reuso@exemplo.com",
            "senha": "senhaOriginal123",
            "empresa_nome": "Empresa Teste",
        },
    )
    client.post("/forgot-password", json={"email": "reuso@exemplo.com"})
    token = emails_enviados[0]["token"]

    r1 = client.post("/reset-password", json={"token": token, "nova_senha": "novaSenha123"})
    assert r1.status_code == 200

    r2 = client.post("/reset-password", json={"token": token, "nova_senha": "outraSenha123"})
    assert r2.status_code == 400
    assert "já foi utilizado" in r2.json()["detail"].lower()


def test_negativo_token_expirado():
    db = TestingSessionLocal()
    cad_resp = client.post(
        "/cadastro",
        json={
            "nome": "Expirado Teste",
            "email": "expirado@exemplo.com",
            "senha": "senhaOriginal123",
            "empresa_nome": "Empresa Teste",
        },
    )
    user_id = cad_resp.json()["usuario"]["id"]

    token_expirado_str = "token_expirado_de_teste_12345"
    db_token = ResetToken(
        token=token_expirado_str,
        usuario_id=user_id,
        criado_em=datetime.now(UTC) - timedelta(minutes=45),
        expira_em=datetime.now(UTC) - timedelta(minutes=15),
        usado=False,
    )
    db.add(db_token)
    db.commit()
    db.close()

    val_resp = client.get(f"/validate-reset-token/{token_expirado_str}")
    assert val_resp.json()["valid"] is False

    reset_resp = client.post(
        "/reset-password",
        json={"token": token_expirado_str, "nova_senha": "novaSenhaExpirada123"},
    )
    assert reset_resp.status_code == 400
    assert "expirou" in reset_resp.json()["detail"].lower()


def test_negativo_token_inexistente():
    reset_resp = client.post(
        "/reset-password",
        json={"token": "token_que_nunca_existiu_999", "nova_senha": "senhaQualquer123"},
    )
    assert reset_resp.status_code == 400
    assert "inválido" in reset_resp.json()["detail"].lower()


def test_forgot_password_falha_de_envio_mantem_resposta_neutra(monkeypatch):
    client.post(
        "/cadastro",
        json={
            "nome": "Falha Smtp",
            "email": "falha@exemplo.com",
            "senha": "senhaOriginal123",
            "empresa_nome": "Empresa Teste",
        },
    )

    def send_quebrado(*args, **kwargs):
        raise ConnectionError("SMTP indisponível")

    monkeypatch.setattr("app.routes.auth.send_password_reset_email", send_quebrado)

    resp = client.post("/forgot-password", json={"email": "falha@exemplo.com"})
    assert resp.status_code == 200
    assert "token" not in resp.json()


def test_forgot_password_limita_solicitacoes_por_usuario(emails_enviados):
    from app.core.config import settings

    client.post(
        "/cadastro",
        json={
            "nome": "Spam Teste",
            "email": "spam@exemplo.com",
            "senha": "senhaOriginal123",
            "empresa_nome": "Empresa Teste",
        },
    )

    for _ in range(settings.RESET_REQUEST_LIMIT + 2):
        resp = client.post("/forgot-password", json={"email": "spam@exemplo.com"})
        assert resp.status_code == 200

    assert len(emails_enviados) == settings.RESET_REQUEST_LIMIT


def test_email_sem_credenciais_smtp_falha_explicitamente(monkeypatch):
    from app.core import email as email_mod

    monkeypatch.setattr(email_mod.settings, "MAILTRAP_USERNAME", "")
    monkeypatch.setattr(email_mod.settings, "MAILTRAP_PASSWORD", "")
    monkeypatch.setattr(email_mod.settings, "EMAIL_LOG_LINK_WITHOUT_SMTP", False)

    with pytest.raises(email_mod.EmailNotConfiguredError):
        email_mod.send_password_reset_email("a@exemplo.com", "tok", "Fulano")

    monkeypatch.setattr(email_mod.settings, "EMAIL_LOG_LINK_WITHOUT_SMTP", True)
    assert email_mod.send_password_reset_email("a@exemplo.com", "tok", "Fulano") is True


def test_email_escapa_html_no_nome_do_usuario(monkeypatch):
    from app.core import email as email_mod

    capturado = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def sendmail(self, frm, to, msg):
            capturado["msg"] = msg

    monkeypatch.setattr(email_mod.settings, "MAILTRAP_USERNAME", "api")
    monkeypatch.setattr(email_mod.settings, "MAILTRAP_PASSWORD", "segredo")
    monkeypatch.setattr(email_mod.smtplib, "SMTP", FakeSMTP)

    assert email_mod.send_password_reset_email("a@exemplo.com", "tok", "<script>x</script>") is True
    # O corpo MIME é base64: decodifica cada parte antes de checar
    mensagem = message_from_string(capturado["msg"])
    html_parte = next(p for p in mensagem.walk() if p.get_content_type() == "text/html")
    corpo = html_parte.get_payload(decode=True).decode("utf-8")
    assert "&lt;script&gt;" in corpo
    assert "<script>" not in corpo


def test_permissao_visualizar_logs_somente_no_papel_admin():
    from app.core.rbac_seed import PAPEIS_DEFINICAO, PERMISSOES_DEFINICAO

    assert {"action": "visualizar", "resource": "logs"}.items() <= next(
        p for p in PERMISSOES_DEFINICAO if p["resource"] == "logs"
    ).items()

    com_permissao = [p["slug"] for p in PAPEIS_DEFINICAO if "visualizar:logs" in p["permissoes"]]
    assert com_permissao == ["admin"]

    # O seed grava a permissão no banco e um usuário comum não a recebe no cadastro
    db = TestingSessionLocal()
    from app.models.permissao import Permissao

    assert db.query(Permissao).filter_by(action="visualizar", resource="logs").count() == 1
    db.close()

    resp = client.post(
        "/cadastro",
        json={
            "nome": "Comum",
            "email": "comum-logs@exemplo.com",
            "senha": "password123",
            "empresa_nome": "Empresa Teste",
            "role": "dono",
        },
    )
    assert "visualizar:logs" not in resp.json()["usuario"]["permissions"]


def _criar_e_logar(email, role, senha="password123"):
    db = TestingSessionLocal()
    user = usuario_repo.create(db, nome=f"User {role}", email=email, senha=senha, role=role)
    user_id = user.id
    db.close()
    token = client.post("/login", data={"username": email, "password": senha}).json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_gestao_de_usuarios_exige_admin():
    alvo_id, _ = _criar_e_logar("alvo@exemplo.com", "cliente")
    _, comum = _criar_e_logar("dono-gestao@exemplo.com", "dono")

    assert client.get("/users", headers=comum).status_code == 403
    assert client.put(f"/users/{alvo_id}/role", json={"role": "admin"}, headers=comum).status_code == 403
    assert (
        client.put(
            f"/users/{alvo_id}/permissions", json={"permissions": ["administrar:sistema"]}, headers=comum
        ).status_code
        == 403
    )
    assert client.delete(f"/users/{alvo_id}", headers=comum).status_code == 403
    assert client.delete(f"/users/{alvo_id}").status_code == 401


def test_admin_altera_papel_e_descarta_ajustes_individuais():
    alvo_id, _ = _criar_e_logar("plano@exemplo.com", "cliente")
    _, admin = _criar_e_logar("admin-plano@exemplo.com", "admin")

    ajuste = client.put(f"/users/{alvo_id}/permissions", json={"permissions": ["visualizar:logs"]}, headers=admin)
    assert ajuste.status_code == 200
    assert ajuste.json()["permissions"] == ["visualizar:logs"]

    resp = client.put(f"/users/{alvo_id}/role", json={"role": "encarregado"}, headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "encarregado"
    # Trocar de papel volta às permissões padrão do novo papel
    assert data["permissions"] == []

    invalido = client.put(f"/users/{alvo_id}/role", json={"role": "papel-fantasma"}, headers=admin)
    assert invalido.status_code == 400


def test_admin_concede_permissoes_individuais():
    alvo_id, _ = _criar_e_logar("perms@exemplo.com", "cliente")
    _, admin = _criar_e_logar("admin-perms@exemplo.com", "admin")

    resp = client.put(f"/users/{alvo_id}/permissions", json={"permissions": ["visualizar:logs"]}, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["permissions"] == ["visualizar:logs"]  # concedida além do papel
    assert resp.json()["role"] == "cliente"

    # O login seguinte já carrega as permissões efetivas no JWT
    login = client.post("/login", data={"username": "perms@exemplo.com", "password": "password123"})
    assert set(login.json()["user"]["permissions"]) == {"visualizar:logs"}

    desconhecida = client.put(f"/users/{alvo_id}/permissions", json={"permissions": ["voar:nave"]}, headers=admin)
    assert desconhecida.status_code == 400
    assert "voar:nave" in desconhecida.json()["detail"]


def test_admin_remove_usuario_e_nao_age_sobre_si_mesmo(emails_enviados):
    alvo_id, _ = _criar_e_logar("remover@exemplo.com", "encarregado")
    admin_id, admin = _criar_e_logar("admin-remove@exemplo.com", "admin")

    # Token de recuperação pendente e ajuste individual não impedem a remoção
    client.post("/forgot-password", json={"email": "remover@exemplo.com"})
    client.put(f"/users/{alvo_id}/permissions", json={"permissions": ["visualizar:logs"]}, headers=admin)

    assert client.delete(f"/users/{alvo_id}", headers=admin).status_code == 204
    assert client.get(f"/users/{alvo_id}").status_code == 404
    assert client.delete(f"/users/{alvo_id}", headers=admin).status_code == 404

    assert client.delete(f"/users/{admin_id}", headers=admin).status_code == 400
    assert client.put(f"/users/{admin_id}/role", json={"role": "cliente"}, headers=admin).status_code == 400

    ids = [u["id"] for u in client.get("/users", headers=admin).json()]
    assert alvo_id not in ids and admin_id in ids


# ── Plano Premium (rotas internas chamadas pelo webhook da API) ──

TOKEN_INTERNO = "token-interno-de-teste"


@pytest.fixture
def interno(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "AUTH_INTERNAL_TOKEN", TOKEN_INTERNO)
    return {"X-Internal-Token": TOKEN_INTERNO}


def _evento(event_id, tipo="checkout.session.completed", **campos):
    return {"event_id": event_id, "tipo": tipo, **campos}


def _usuario_no_banco(user_id):
    db = TestingSessionLocal()
    try:
        u = db.get(Usuario, user_id)
        return {
            "premium": u.premium,
            "customer": u.stripe_customer_id,
            "subscription": u.stripe_subscription_id,
            "desde": u.premium_desde,
        }
    finally:
        db.close()


def test_usuario_novo_nao_e_premium():
    user_id, headers = _criar_e_logar("free@exemplo.com", "dono")
    assert client.get("/me", headers=headers).json()["premium"] is False
    assert client.get(f"/users/{user_id}").json()["premium"] is False


def test_rota_interna_exige_token(monkeypatch, interno):
    corpo = _evento("evt_sem_token", usuario_id=1)
    assert client.post("/internal/premium/eventos", json=corpo).status_code == 401
    assert (
        client.post("/internal/premium/eventos", json=corpo, headers={"X-Internal-Token": "errado"}).status_code == 401
    )

    from app.core.config import settings

    monkeypatch.setattr(settings, "AUTH_INTERNAL_TOKEN", "")
    assert client.post("/internal/premium/eventos", json=corpo, headers=interno).status_code == 503


def test_checkout_concluido_ativa_premium_e_guarda_so_ids(interno):
    user_id, headers = _criar_e_logar("assinante@exemplo.com", "dono")

    resp = client.post(
        "/internal/premium/eventos",
        json=_evento("evt_1", usuario_id=user_id, customer_id="cus_123", subscription_id="sub_123"),
        headers=interno,
    )
    assert resp.status_code == 200
    assert resp.json() == {"duplicado": False, "aplicado": True, "usuario_id": user_id, "premium": True}

    banco = _usuario_no_banco(user_id)
    assert banco["premium"] is True
    assert (banco["customer"], banco["subscription"]) == ("cus_123", "sub_123")
    assert banco["desde"] is not None
    assert client.get("/me", headers=headers).json()["premium"] is True


def test_evento_repetido_e_processado_uma_vez(interno):
    user_id, _ = _criar_e_logar("repetido@exemplo.com", "dono")
    corpo = _evento("evt_dup", usuario_id=user_id, customer_id="cus_d", subscription_id="sub_d")

    assert client.post("/internal/premium/eventos", json=corpo, headers=interno).json()["aplicado"] is True

    # Cancela por outro evento e reenvia o primeiro: o reenvio não pode reativar
    client.post(
        "/internal/premium/eventos",
        json=_evento("evt_cancel", tipo="customer.subscription.deleted", subscription_id="sub_d"),
        headers=interno,
    )
    reenvio = client.post("/internal/premium/eventos", json=corpo, headers=interno)
    assert reenvio.json() == {"duplicado": True, "aplicado": False, "usuario_id": None, "premium": None}
    assert _usuario_no_banco(user_id)["premium"] is False


def test_assinatura_cancelada_remove_premium(interno):
    user_id, _ = _criar_e_logar("cancela@exemplo.com", "dono")
    client.post(
        "/internal/premium/eventos",
        json=_evento("evt_a", usuario_id=user_id, customer_id="cus_c", subscription_id="sub_c"),
        headers=interno,
    )

    # Assinatura que não é a atual do usuário: nada muda
    outra = client.post(
        "/internal/premium/eventos",
        json=_evento("evt_b", tipo="customer.subscription.deleted", subscription_id="sub_antiga"),
        headers=interno,
    )
    assert outra.json()["aplicado"] is False
    assert _usuario_no_banco(user_id)["premium"] is True

    resp = client.post(
        "/internal/premium/eventos",
        json=_evento("evt_c", tipo="customer.subscription.deleted", subscription_id="sub_c"),
        headers=interno,
    )
    assert resp.json() == {"duplicado": False, "aplicado": True, "usuario_id": user_id, "premium": False}
    banco = _usuario_no_banco(user_id)
    assert banco["premium"] is False and banco["subscription"] is None
    # O customer fica: numa nova assinatura o Stripe reaproveita o mesmo cliente
    assert banco["customer"] == "cus_c"


def test_evento_de_usuario_inexistente_e_registrado_sem_erro(interno):
    resp = client.post("/internal/premium/eventos", json=_evento("evt_fantasma", usuario_id=99999), headers=interno)
    assert resp.status_code == 200
    assert resp.json()["aplicado"] is False
    # Registrado: o reenvio do Stripe não fica em loop
    assert (
        client.post(
            "/internal/premium/eventos", json=_evento("evt_fantasma", usuario_id=99999), headers=interno
        ).json()["duplicado"]
        is True
    )


def test_rota_interna_recusa_tipo_de_evento_desconhecido(interno):
    resp = client.post("/internal/premium/eventos", json=_evento("evt_x", tipo="invoice.paid"), headers=interno)
    assert resp.status_code == 422


# ── Identidade por vínculo (Fase 3, ADR 004) ─────────────────────────────────


def _claims(token: str) -> dict:
    from jose import jwt

    return jwt.decode(token, os.environ["SECRET_KEY"], algorithms=["HS256"])


def _cadastrar(email, empresa="Rocha Reformas", **extras):
    corpo = {"nome": "Pessoa Teste", "email": email, "senha": "senha123", "empresa_nome": empresa, **extras}
    return client.post("/cadastro", json=corpo)


def _logar(email, senha="senha123"):
    return client.post("/login", data={"username": email, "password": senha})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_cadastro_cria_empresa_usuario_e_vinculo_dono_numa_transacao():
    from app.models.empresa import Empresa, Vinculo

    resp = _cadastrar("valdir@exemplo.com", "Rocha Reformas", tipo_pessoa="PJ", documento="12.345.678/0001-90")
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["empresa"]["nome"] == "Rocha Reformas"
    assert corpo["empresa"]["tipo_pessoa"] == "PJ"
    assert corpo["empresa"]["documento"] == "12345678000190"  # só os dígitos

    db = TestingSessionLocal()
    vinculo = db.query(Vinculo).one()
    assert vinculo.usuario_id == corpo["usuario"]["id"] and vinculo.papel == "dono" and vinculo.ativo
    assert str(vinculo.empresa_id) == corpo["empresa"]["id"]
    assert db.query(Empresa).count() == 1
    db.close()


def test_cadastro_com_email_existente_orienta_a_criar_empresa_logado():
    _cadastrar("repetido@exemplo.com")
    resp = _cadastrar("repetido@exemplo.com", "Outra Empresa")
    assert resp.status_code == 409
    assert "/auth/empresas" in resp.json()["detail"]


@pytest.mark.parametrize(
    "tipo, documento",
    [("PF", "123"), ("PJ", "123.456.789-01"), ("PF", "12.345.678/0001-90")],
)
def test_documento_precisa_ter_os_digitos_do_tipo_de_pessoa(tipo, documento):
    resp = _cadastrar(f"doc-{tipo}-{len(documento)}@exemplo.com", tipo_pessoa=tipo, documento=documento)
    assert resp.status_code == 422


def test_documento_repetido_e_recusado_sem_criar_usuario():
    assert _cadastrar("a@exemplo.com", tipo_pessoa="PF", documento="123.456.789-01").status_code == 201
    resp = _cadastrar("b@exemplo.com", tipo_pessoa="PF", documento="12345678901")
    assert resp.status_code == 409
    assert _logar("b@exemplo.com").status_code == 401  # nada ficou pela metade


def test_login_traz_o_vinculo_no_token_e_no_contexto():
    cad = _cadastrar("dono@exemplo.com", "Construtora Horizonte").json()
    resp = _logar("dono@exemplo.com").json()

    claims = _claims(resp["access_token"])
    assert claims["sub"] == str(cad["usuario"]["id"])
    assert claims["empresa_id"] == cad["empresa"]["id"]
    assert claims["papel"] == "dono"
    assert claims["admin"] is False
    assert resp["contexto"] == {
        "empresa_id": cad["empresa"]["id"],
        "empresa_nome": "Construtora Horizonte",
        "papel": "dono",
    }


def test_token_dura_duas_horas():
    from datetime import datetime

    _cadastrar("validade@exemplo.com")
    claims = _claims(_logar("validade@exemplo.com").json()["access_token"])
    duracao = datetime.fromtimestamp(claims["exp"], UTC) - datetime.now(UTC)
    assert timedelta(minutes=115) < duracao <= timedelta(minutes=120)


def _usuario_sem_vinculo(email="sem-vinculo@exemplo.com"):
    db = TestingSessionLocal()
    usuario_repo.create(db, nome="Sem Vínculo", email=email, senha="senha123")
    db.close()
    return _logar(email).json()


def test_usuario_sem_vinculo_recebe_token_sem_tenant():
    resp = _usuario_sem_vinculo()
    claims = _claims(resp["access_token"])
    assert claims["empresa_id"] is None and claims["papel"] is None
    assert resp["contexto"] is None

    token = resp["access_token"]
    assert client.get("/vinculos", headers=_auth(token)).json() == []


def test_token_sem_tenant_cria_empresa_e_recebe_token_com_ela_ativa():
    token = _usuario_sem_vinculo()["access_token"]
    resp = client.post("/empresas", json={"nome": "Minha Empresa", "tipo_pessoa": "PF"}, headers=_auth(token))

    assert resp.status_code == 201
    corpo = resp.json()
    claims = _claims(corpo["access_token"])
    assert claims["empresa_id"] == corpo["empresa"]["id"] and claims["papel"] == "dono"
    vinculos = client.get("/vinculos", headers=_auth(corpo["access_token"])).json()
    assert [(v["empresa_nome"], v["papel"], v["ativa"]) for v in vinculos] == [("Minha Empresa", "dono", True)]


def test_empresa_ativa_troca_de_empresa_e_recusa_empresa_alheia():
    cad = _cadastrar("multi@exemplo.com", "Empresa A").json()
    token_a = _logar("multi@exemplo.com").json()["access_token"]
    empresa_b = client.post("/empresas", json={"nome": "Empresa B"}, headers=_auth(token_a)).json()["empresa"]
    outra = _cadastrar("alheio@exemplo.com", "Empresa de Outro").json()["empresa"]

    troca = client.post("/empresa-ativa", json={"empresa_id": cad["empresa"]["id"]}, headers=_auth(token_a))
    assert troca.status_code == 200
    assert _claims(troca.json()["access_token"])["empresa_id"] == cad["empresa"]["id"]

    troca_b = client.post("/empresa-ativa", json={"empresa_id": empresa_b["id"]}, headers=_auth(token_a))
    assert _claims(troca_b.json()["access_token"])["empresa_id"] == empresa_b["id"]

    # Sem vínculo: 404, sem revelar que a empresa existe
    alheia = client.post("/empresa-ativa", json={"empresa_id": outra["id"]}, headers=_auth(token_a))
    assert alheia.status_code == 404


def test_login_escolhe_o_vinculo_mais_recente():
    _cadastrar("recente@exemplo.com", "Primeira")
    token = _logar("recente@exemplo.com").json()["access_token"]
    segunda = client.post("/empresas", json={"nome": "Segunda"}, headers=_auth(token)).json()["empresa"]
    assert _logar("recente@exemplo.com").json()["contexto"]["empresa_id"] == segunda["id"]


def test_vinculo_desativado_some_do_login_e_da_troca():
    from app.models.empresa import Vinculo

    cad = _cadastrar("desligado@exemplo.com", "Empresa X").json()
    token = _logar("desligado@exemplo.com").json()["access_token"]

    db = TestingSessionLocal()
    db.query(Vinculo).update({"ativo": False})
    db.commit()
    db.close()

    assert _logar("desligado@exemplo.com").json()["contexto"] is None
    assert client.get("/vinculos", headers=_auth(token)).json() == []
    troca = client.post("/empresa-ativa", json={"empresa_id": cad["empresa"]["id"]}, headers=_auth(token))
    assert troca.status_code == 403


def test_admin_criado_por_variavel_de_ambiente_e_idempotente():
    from app.core.admin import garantir_admin

    db = TestingSessionLocal()
    admin = garantir_admin(db, "Admin@Nivelo.app", "uma-senha-bem-longa")
    assert admin.admin_plataforma is True and admin.email == "admin@nivelo.app"
    # Reiniciar não troca a senha nem duplica
    garantir_admin(db, "admin@nivelo.app", "outra-senha-qualquer")
    db.close()
    assert _logar("admin@nivelo.app", "uma-senha-bem-longa").status_code == 200
    assert _logar("admin@nivelo.app", "outra-senha-qualquer").status_code == 401

    resp = _logar("admin@nivelo.app", "uma-senha-bem-longa").json()
    claims = _claims(resp["access_token"])
    assert claims["admin"] is True and claims["empresa_id"] is None
    assert resp["user"]["admin"] is True


def test_admin_promove_usuario_existente_e_recusa_senha_curta():
    from app.core.admin import garantir_admin

    _cadastrar("vira-admin@exemplo.com")
    db = TestingSessionLocal()
    assert garantir_admin(db, "vira-admin@exemplo.com", "senha-ignorada-123").admin_plataforma is True
    assert garantir_admin(db, "", "") is None
    with pytest.raises(ValueError):
        garantir_admin(db, "novo@exemplo.com", "curta")
    db.close()


def test_admin_da_plataforma_nao_cria_empresa():
    from app.core.admin import garantir_admin

    db = TestingSessionLocal()
    garantir_admin(db, "admin2@nivelo.app", "uma-senha-bem-longa")
    db.close()
    token = _logar("admin2@nivelo.app", "uma-senha-bem-longa").json()["access_token"]
    assert client.post("/empresas", json={"nome": "Indevida"}, headers=_auth(token)).status_code == 403
