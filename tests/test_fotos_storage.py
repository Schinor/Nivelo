"""Fotos do diário no storage: o adaptador S3 (moto no lugar do Garage) e o PUT da ponte
/storage, por onde o navegador envia o arquivo com a URL pré-assinada."""

import uuid
from urllib.parse import parse_qs, urlsplit

import pytest
from test_perfis import BUCKET, _mock_garage
from test_perfis import ctx as ctx  # noqa: F401 — fixture com moto e o app da API

EMPRESA = "0190f3a0-0000-7000-8000-00000000000a"
CHAVE = f"empresas/{EMPRESA}/obras/{uuid.uuid4()}/diarios/{uuid.uuid4()}/{uuid.uuid4()}.jpg"


@pytest.fixture
def garage(ctx):  # noqa: F811
    from app.obras.infrastructure.armazenamento import ArmazenamentoNoGarage

    ctx.garage = ArmazenamentoNoGarage()
    return ctx


def test_url_de_envio_e_relativa_a_api_assina_o_content_type_e_vale_5_min(garage):
    url = garage.garage.url_para_enviar(CHAVE, "image/jpeg", 300)
    partes = urlsplit(url)
    assert partes.path == f"/storage/{BUCKET}/{CHAVE}"
    query = parse_qs(partes.query)
    assert query["X-Amz-Expires"] == ["300"] and "X-Amz-Signature" in query
    assert "content-type" in query["X-Amz-SignedHeaders"][0]


def test_metadados_do_objeto_enviado_e_none_quando_nao_existe(garage):
    from app.services import storage

    assert garage.garage.metadados(CHAVE) is None
    storage.get_client().put_object(Bucket=BUCKET, Key=CHAVE, Body=b"x" * 1234, ContentType="image/jpeg")
    meta = garage.garage.metadados(CHAVE)
    assert (meta.tamanho_bytes, meta.content_type) == (1234, "image/jpeg")
    url = garage.garage.url_para_ler(CHAVE, 600)
    assert url.startswith(f"/storage/{BUCKET}/{CHAVE}?") and "X-Amz-Expires=600" in url
    garage.garage.apagar(CHAVE)
    assert garage.garage.metadados(CHAVE) is None


# ── PUT na ponte /storage ────────────────────────────────────────────────────


def test_put_repassa_corpo_e_content_type_ao_garage_com_a_query_intacta(garage, monkeypatch):
    import httpx

    recebidos = []

    def handler(request):
        recebidos.append(request)
        return httpx.Response(200, headers={"etag": '"abc"'})

    _mock_garage(monkeypatch, handler)
    url = garage.garage.url_para_enviar(CHAVE, "image/jpeg", 300)
    resp = garage.client.put(url, content=b"\xff\xd8 jpeg", headers={"Content-Type": "image/jpeg"})
    assert resp.status_code == 200 and resp.headers["etag"] == '"abc"'
    [enviado] = recebidos
    assert enviado.method == "PUT" and enviado.content == b"\xff\xd8 jpeg"
    assert enviado.headers["content-type"] == "image/jpeg"
    assert enviado.url.raw_path.decode() == url[len("/storage") :]


def test_put_so_aceita_chave_de_foto_assinada_e_ate_5_mb(garage, monkeypatch):
    import httpx

    _mock_garage(monkeypatch, lambda request: httpx.Response(200))
    jpeg = {"Content-Type": "image/jpeg"}
    assert garage.client.put(f"/storage/{BUCKET}/avatares/1/x.webp?X-Amz-Signature=a", content=b"x").status_code == 404
    assert garage.client.put(f"/storage/{BUCKET}/{CHAVE}", content=b"x", headers=jpeg).status_code == 403
    grande = garage.client.put(
        f"/storage/{BUCKET}/{CHAVE}?X-Amz-Signature=a", content=b"x" * (5 * 1024 * 1024 + 1), headers=jpeg
    )
    assert grande.status_code == 413


def test_put_com_assinatura_recusada_pelo_garage_devolve_403(garage, monkeypatch):
    import httpx

    _mock_garage(monkeypatch, lambda request: httpx.Response(403, content=b"<Error>SignatureDoesNotMatch</Error>"))
    resp = garage.client.put(f"/storage/{BUCKET}/{CHAVE}?X-Amz-Signature=errada", content=b"x")
    assert resp.status_code == 403
