"""Atividade 6 — perfil com foto em object storage (Garage/S3).

O S3 é simulado com moto (mock_aws); o auth-service (nome do usuário) e o
log-service são trocados por fakes em memória, no mesmo padrão de test_backend_proxy.
"""

from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
from moto import mock_aws
from test_backend_proxy import _capturar_eventos, _usuario, setup_api_app

BUCKET = "catalogo-avatares"
USUARIOS = {1: "Ana", 2: "Beto", 9: "Admin"}


def _imagem(formato="PNG", tamanho=(100, 80), cor=(200, 30, 30)):
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", tamanho, cor).save(buffer, format=formato)
    return buffer.getvalue()


@pytest.fixture
def ctx(monkeypatch):
    with mock_aws():
        import boto3
        from fastapi import HTTPException

        app, SessionLocal, current_user, TestClient = setup_api_app()
        from botocore.config import Config

        from app.services import storage

        # Mesma configuração do cliente real (SigV4 + path-style), sem endpoint custom: o moto intercepta
        s3 = boto3.client(
            "s3",
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        s3.create_bucket(Bucket=BUCKET)
        storage.get_client.cache_clear()
        monkeypatch.setattr(storage, "get_client", lambda: s3)

        async def fake_forward(method, path, **kw):
            uid = int(path.rsplit("/", 1)[1])
            if uid not in USUARIOS:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")
            return {"id": uid, "nome": USUARIOS[uid], "email": f"u{uid}@teste.com"}

        monkeypatch.setattr("app.routes.perfis.forward_request", fake_forward)
        from app.clients import log_client

        registrar_real = log_client.registrar
        eventos = _capturar_eventos(monkeypatch)

        class Ctx:
            pass

        c = Ctx()
        c.app, c.SessionLocal, c.s3, c.eventos, c.storage = app, SessionLocal, s3, eventos, storage
        c.registrar_real = registrar_real
        c.client = TestClient(app)

        def logar(uid, role="dono", permissions=()):
            app.dependency_overrides[current_user] = lambda: _usuario(uid, role)

        c.logar = logar
        yield c


def _objetos(s3):
    return [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])]


def _perfil_no_banco(ctx, uid):
    from app.models.perfil import Perfil

    db = ctx.SessionLocal()
    try:
        perfil = db.get(Perfil, uid)
        return (
            None
            if perfil is None
            else {"bio": perfil.bio, "foto_key": perfil.foto_key, "foto_bytes": perfil.foto_bytes}
        )
    finally:
        db.close()


def _enviar(ctx, uid, dados, nome="foto.png", tipo="image/png"):
    return ctx.client.put(f"/api/perfis/{uid}/foto", files={"foto": (nome, dados, tipo)})


# ── storage.py ────────────────────────────────────────────────────────────────


def test_calcular_expiracao_tempo_mais_margem_com_teto_e_piso(monkeypatch):
    setup_api_app()
    from app.core.config import settings
    from app.services import storage

    # 64 KB a 256 kbps ≈ 2,05 s → 3 s + 600 s de margem
    assert storage.calcular_expiracao(64 * 1024) == 3 + 600
    # Arquivo gigante: bate no teto
    assert storage.calcular_expiracao(10**12) == 3600

    # Nunca abaixo de 60 s, mesmo sem margem
    monkeypatch.setattr(settings, "STORAGE_MARGEM_USO_SEGUNDOS", 0)
    assert storage.calcular_expiracao(0) == 60


def test_url_assinada_aponta_para_a_ponte_storage(ctx):
    url = ctx.storage.url_assinada("avatares/1/abc.webp", 60_000)
    assert url.startswith("/storage/catalogo-avatares/avatares/")
    query = parse_qs(urlsplit(url).query)
    assert "X-Amz-Signature" in query
    assert query["X-Amz-Expires"] == ["602"]


# ── GET ───────────────────────────────────────────────────────────────────────


def test_get_perfil_exige_token(ctx):
    assert ctx.client.get("/api/perfis/1").status_code == 401
    assert ctx.client.get("/api/perfis/me").status_code == 401


def test_get_perfil_inexistente_retorna_404(ctx):
    ctx.logar(1)
    assert ctx.client.get("/api/perfis/404").status_code == 404


def test_get_perfil_sem_linha_e_pode_editar_so_para_o_dono(ctx):
    # Usuário 1 vê o perfil do 2
    ctx.logar(1)
    resp = ctx.client.get("/api/perfis/2")
    assert resp.status_code == 200
    assert resp.json() == {
        "usuario_id": 2,
        "nome": "Beto",
        "bio": None,
        "foto_url": None,
        "pode_editar": False,
        "premium": False,
    }

    ctx.logar(2)
    assert ctx.client.get("/api/perfis/2").json()["pode_editar"] is True
    me = ctx.client.get("/api/perfis/me").json()
    assert me["usuario_id"] == 2 and me["pode_editar"] is True


# ── PUT bio ───────────────────────────────────────────────────────────────────


def test_dono_atualiza_bio(ctx):
    ctx.logar(1)
    resp = ctx.client.put("/api/perfis/1", json={"bio": "  Fã de Náufrago  "})
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Fã de Náufrago"
    assert ctx.eventos[-1] == {"acao": "perfil_atualizado", "usuario_id": 1, "recurso": "perfil:1", "detalhes": None}

    # String vazia vira NULL
    assert ctx.client.put("/api/perfis/1", json={"bio": "   "}).json()["bio"] is None
    assert _perfil_no_banco(ctx, 1)["bio"] is None


def test_outro_usuario_nao_edita_bio_alheia(ctx):
    ctx.logar(2)
    resp = ctx.client.put("/api/perfis/1", json={"bio": "invasão"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Você só pode editar o próprio perfil"
    assert _perfil_no_banco(ctx, 1) is None
    assert ctx.eventos[-1] == {
        "acao": "acesso.negado",
        "usuario_id": 2,
        "recurso": "perfil:1",
        "detalhes": "PUT /api/perfis/1",
    }


def test_admin_tambem_recebe_403_em_perfil_alheio(ctx):
    ctx.logar(9, "admin", ["administrar:sistema", "gerenciar:usuarios"])
    assert ctx.client.put("/api/perfis/1", json={"bio": "sou admin"}).status_code == 403
    assert _enviar(ctx, 1, _imagem()).status_code == 403
    assert ctx.client.delete("/api/perfis/1/foto").status_code == 403
    assert _perfil_no_banco(ctx, 1) is None


def test_bio_maior_que_280_retorna_422(ctx):
    ctx.logar(1)
    assert ctx.client.put("/api/perfis/1", json={"bio": "x" * 281}).status_code == 422
    assert ctx.client.put("/api/perfis/1", json={"bio": "x" * 280}).status_code == 200


def test_usuario_id_no_corpo_e_ignorado(ctx):
    ctx.logar(1)
    resp = ctx.client.put("/api/perfis/1", json={"bio": "minha", "usuario_id": 2})
    assert resp.status_code == 200
    assert _perfil_no_banco(ctx, 1)["bio"] == "minha"
    assert _perfil_no_banco(ctx, 2) is None


# ── Upload ────────────────────────────────────────────────────────────────────


def test_upload_png_valido_grava_webp_e_so_a_chave_no_banco(ctx):
    ctx.logar(1)
    resp = _enviar(ctx, 1, _imagem("PNG", (900, 400)))
    assert resp.status_code == 200

    banco = _perfil_no_banco(ctx, 1)
    chave = banco["foto_key"]
    assert chave.startswith("avatares/1/") and chave.endswith(".webp")
    assert "://" not in chave and "?" not in chave  # só a chave, nunca a URL
    assert _objetos(ctx.s3) == [chave]

    objeto = ctx.s3.get_object(Bucket=BUCKET, Key=chave)
    assert objeto["ContentType"] == "image/webp"
    corpo = objeto["Body"].read()
    assert banco["foto_bytes"] == len(corpo)

    from PIL import Image

    with Image.open(BytesIO(corpo)) as img:
        assert img.format == "WEBP" and img.size == (512, 512)

    foto_url = resp.json()["foto_url"]
    assert foto_url.startswith(f"/storage/{BUCKET}/{chave}?")
    assert "X-Amz-Signature=" in foto_url
    assert ctx.eventos[-1] == {
        "acao": "perfil_foto_atualizada",
        "usuario_id": 1,
        "recurso": "perfil:1",
        "detalhes": chave,
    }


def test_upload_remove_exif(ctx):
    from PIL import Image

    img = Image.new("RGB", (50, 50))
    exif = Image.Exif()
    exif[0x010F] = "CameraSecreta"  # Make
    buffer = BytesIO()
    img.save(buffer, format="JPEG", exif=exif)

    ctx.logar(1)
    assert _enviar(ctx, 1, buffer.getvalue(), "f.jpg", "image/jpeg").status_code == 200
    corpo = ctx.s3.get_object(Bucket=BUCKET, Key=_objetos(ctx.s3)[0])["Body"].read()
    assert b"CameraSecreta" not in corpo


def test_upload_em_perfil_alheio_retorna_403_e_nada_e_gravado(ctx):
    ctx.logar(2)
    assert _enviar(ctx, 1, _imagem()).status_code == 403
    assert _objetos(ctx.s3) == []
    assert _perfil_no_banco(ctx, 1) is None
    assert ctx.eventos[-1]["acao"] == "acesso.negado"
    assert ctx.eventos[-1]["recurso"] == "perfil:1"


def test_upload_maior_que_o_limite_retorna_413(ctx, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PERFIL_FOTO_MAX_BYTES", 1024)
    ctx.logar(1)
    resp = _enviar(ctx, 1, _imagem("PNG", (300, 300)) + b"\0" * 2048)
    assert resp.status_code == 413
    assert _objetos(ctx.s3) == []


def test_upload_vazio_retorna_400(ctx):
    ctx.logar(1)
    assert _enviar(ctx, 1, b"").status_code == 400


@pytest.mark.parametrize(
    "dados,nome,tipo",
    [
        (b"isto nao e uma imagem, so texto", "foto.png", "image/png"),  # extensão e content-type mentem
        (_imagem("GIF"), "foto.gif", "image/gif"),  # imagem real, formato fora da lista
        (_imagem("PNG")[:40], "cortada.png", "image/png"),  # PNG truncado
    ],
)
def test_upload_de_tipo_invalido_retorna_415(ctx, dados, nome, tipo):
    ctx.logar(1)
    resp = _enviar(ctx, 1, dados, nome, tipo)
    assert resp.status_code == 415
    assert resp.json()["detail"] == "Envie uma imagem JPEG, PNG ou WEBP"
    assert _objetos(ctx.s3) == []


def test_upload_de_bomba_de_descompressao_retorna_415(ctx, monkeypatch):
    from PIL import Image

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # 100x80 = 8000 px > 2x o limite
    ctx.logar(1)
    assert _enviar(ctx, 1, _imagem("PNG", (100, 80))).status_code == 415


def test_segundo_upload_apaga_o_objeto_antigo(ctx):
    ctx.logar(1)
    _enviar(ctx, 1, _imagem(cor=(1, 2, 3)))
    primeira = _perfil_no_banco(ctx, 1)["foto_key"]
    _enviar(ctx, 1, _imagem(cor=(4, 5, 6)))
    segunda = _perfil_no_banco(ctx, 1)["foto_key"]

    assert primeira != segunda
    assert _objetos(ctx.s3) == [segunda]


def test_falha_do_storage_retorna_502_e_banco_intocado(ctx, monkeypatch):
    from botocore.exceptions import ClientError

    ctx.logar(1)
    ctx.client.put("/api/perfis/1", json={"bio": "antes"})

    def quebrado(*a, **kw):
        raise ClientError({"Error": {"Code": "ServiceUnavailable", "Message": "fora"}}, "PutObject")

    monkeypatch.setattr(ctx.storage, "enviar_objeto", quebrado)
    resp = _enviar(ctx, 1, _imagem())
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Storage indisponível"
    assert _perfil_no_banco(ctx, 1) == {"bio": "antes", "foto_key": None, "foto_bytes": None}


def test_limite_de_uploads_por_minuto(ctx):
    from app.routes import perfis

    ctx.logar(1)
    for _ in range(perfis.UPLOADS_POR_MINUTO):
        assert _enviar(ctx, 1, _imagem()).status_code == 200
    assert _enviar(ctx, 1, _imagem()).status_code == 429


def test_log_service_fora_nao_quebra_o_upload(ctx, monkeypatch):
    from app.clients import log_client
    from app.core.config import settings

    # Cliente real do log-service, apontando para uma porta fechada
    monkeypatch.setattr(log_client, "registrar", ctx.registrar_real)
    monkeypatch.setattr(settings, "LOG_SERVICE_URL", "http://127.0.0.1:9")

    ctx.logar(1)
    assert _enviar(ctx, 1, _imagem()).status_code == 200
    ctx.logar(2)
    assert _enviar(ctx, 1, _imagem()).status_code == 403


# ── DELETE foto ───────────────────────────────────────────────────────────────


def test_remover_foto_apaga_banco_e_bucket_e_e_idempotente(ctx):
    ctx.logar(1)
    _enviar(ctx, 1, _imagem())
    assert len(_objetos(ctx.s3)) == 1

    assert ctx.client.delete("/api/perfis/1/foto").status_code == 204
    assert _perfil_no_banco(ctx, 1)["foto_key"] is None
    assert _objetos(ctx.s3) == []
    assert ctx.eventos[-1] == {"acao": "perfil_foto_removida", "usuario_id": 1, "recurso": "perfil:1", "detalhes": None}

    total = len(ctx.eventos)
    assert ctx.client.delete("/api/perfis/1/foto").status_code == 204
    assert len(ctx.eventos) == total  # sem foto, nada a registrar


def test_admin_remove_usuario_apaga_perfil_e_foto(ctx, monkeypatch):
    ctx.logar(1)
    _enviar(ctx, 1, _imagem())

    async def auth_ok(method, path, **kw):
        return None

    monkeypatch.setattr("app.routes.auth.forward_request", auth_ok)
    ctx.logar(9, "admin", ["gerenciar:usuarios"])
    assert ctx.client.delete("/api/auth/users/1").status_code == 204
    assert _perfil_no_banco(ctx, 1) is None
    assert _objetos(ctx.s3) == []


# ── Ponte /storage ────────────────────────────────────────────────────────────


def _corpo_em_stream(dados):
    """Corpo ainda não lido, como o de uma resposta real (httpx.Response(content=...) já nasce consumido)."""
    import httpx

    class CorpoEmStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield dados

    return CorpoEmStream()


def _mock_garage(monkeypatch, handler):
    import httpx

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.routes.storage_proxy.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )


def test_ponte_storage_sem_assinatura_retorna_403(ctx):
    resp = ctx.client.get(f"/storage/{BUCKET}/x.webp")
    assert resp.status_code == 403


def test_ponte_storage_bucket_errado_retorna_404(ctx):
    resp = ctx.client.get("/storage/outro-bucket/x.webp?X-Amz-Signature=abc")
    assert resp.status_code == 404


def test_ponte_storage_repassa_caminho_e_query_intactos(ctx, monkeypatch):
    import httpx

    recebidos = []

    def handler(request):
        recebidos.append(request)
        return httpx.Response(
            200,
            stream=_corpo_em_stream(b"RIFF....WEBP"),
            headers={"content-type": "image/webp", "x-amz-id": "nao-repassar"},
        )

    _mock_garage(monkeypatch, handler)
    url = ctx.storage.url_assinada("avatares/1/a b%.webp", 1000)
    resp = ctx.client.get(url)

    assert resp.status_code == 200
    assert resp.content == b"RIFF....WEBP"
    assert resp.headers["content-type"] == "image/webp"
    assert resp.headers["cache-control"] == "private, max-age=300"
    assert "x-amz-id" not in resp.headers

    enviado = recebidos[0].url
    assert f"{enviado.scheme}://{enviado.netloc.decode()}" == ctx.storage.STORAGE_ENDPOINT
    # Byte a byte igual ao que foi assinado (sem decodificar/recodificar)
    assert enviado.raw_path.decode() == url[len("/storage") :]


def test_ponte_storage_repassa_403_do_upstream(ctx, monkeypatch):
    import httpx

    _mock_garage(
        monkeypatch, lambda request: httpx.Response(403, stream=_corpo_em_stream(b"<Error>AccessDenied</Error>"))
    )
    resp = ctx.client.get(f"/storage/{BUCKET}/x.webp?X-Amz-Signature=adulterada")
    assert resp.status_code == 403
    assert "cache-control" not in resp.headers


def test_ponte_storage_upstream_fora_retorna_502(ctx, monkeypatch):
    import httpx

    def handler(request):
        raise httpx.ConnectError("sem rota", request=request)

    _mock_garage(monkeypatch, handler)
    assert ctx.client.get(f"/storage/{BUCKET}/x.webp?X-Amz-Signature=abc").status_code == 502
