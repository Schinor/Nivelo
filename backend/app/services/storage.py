"""Acesso ao object storage da API (Garage, via API S3 com boto3).

O banco guarda só a CHAVE do objeto (ex.: "avatares/42/9f1c....webp").
A URL é montada na hora de exibir, pré-assinada e com expiração.

Assinamos com o host INTERNO (garage:3900) e devolvemos a URL com o prefixo
/storage da API. A rota /storage (app.routes.storage_proxy) repassa a
requisição intacta ao Garage, que é quem valida assinatura e expiração.
"""

from __future__ import annotations

import math
from functools import lru_cache
from urllib.parse import urlsplit

import boto3
from botocore.config import Config

from app.core.config import settings

STORAGE_ENDPOINT = settings.STORAGE_ENDPOINT.rstrip("/")
STORAGE_BUCKET = settings.STORAGE_BUCKET
STORAGE_PUBLIC_PREFIX = "/storage"

EXPIRACAO_MIN_S = 60


@lru_cache(maxsize=1)
def get_client():
    """Cliente S3 criado sob demanda (facilita trocar por moto nos testes)."""
    return boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        region_name=settings.STORAGE_REGION,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # http://garage:3900/<bucket>/<chave>
        ),
    )


def calcular_expiracao(tamanho_bytes: int) -> int:
    """Validade = tempo de download na pior conexão aceita + margem de uso da página.

    - tempo de download: tamanho / banda mínima (60 KB a 256 kbps ≈ 2 s)
    - margem de uso: a página fica aberta, o usuário rola, volta, recarrega
    - teto: limita a janela em que um link vazado continua válido
    """
    bits = max(tamanho_bytes, 1) * 8
    tempo_download_s = math.ceil(bits / (settings.STORAGE_BANDA_MINIMA_KBPS * 1000))
    return max(
        EXPIRACAO_MIN_S,
        min(tempo_download_s + settings.STORAGE_MARGEM_USO_SEGUNDOS, settings.STORAGE_EXPIRACAO_MAX_SEGUNDOS),
    )


def enviar_objeto(chave: str, dados: bytes, content_type: str) -> None:
    get_client().put_object(Bucket=STORAGE_BUCKET, Key=chave, Body=dados, ContentType=content_type)


def apagar_objeto(chave: str) -> None:
    get_client().delete_object(Bucket=STORAGE_BUCKET, Key=chave)


def url_assinada(chave: str, tamanho_bytes: int) -> str:
    """URL RELATIVA à API:
    /storage/catalogo-avatares/avatares/42/abc.webp?X-Amz-Algorithm=...&X-Amz-Signature=...
    """
    url = get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": STORAGE_BUCKET, "Key": chave},
        ExpiresIn=calcular_expiracao(tamanho_bytes),
    )
    partes = urlsplit(url)  # descarta só o "http://garage:3900"
    return f"{STORAGE_PUBLIC_PREFIX}{partes.path}?{partes.query}"
