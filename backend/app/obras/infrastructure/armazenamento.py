"""Adaptador da porta `ArmazenamentoDeFotos` para o Garage (API S3, via boto3).

As URLs são assinadas com o host interno (garage:3900) e devolvidas com o prefixo /storage da
API: a ponte `app.routes.storage_proxy` repassa GET e PUT intactos ao Garage, que confere a
assinatura e a validade. O Garage continua sem porta publicada.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from botocore.exceptions import ClientError

from app.obras.application.portas import MetadadosDoObjeto
from app.services import storage


def _relativa(url: str) -> str:
    partes = urlsplit(url)  # descarta só o "http://garage:3900"
    return f"{storage.STORAGE_PUBLIC_PREFIX}{partes.path}?{partes.query}"


class ArmazenamentoNoGarage:
    def url_para_enviar(self, chave: str, content_type: str, validade_s: int) -> str:
        url = storage.get_client().generate_presigned_url(
            "put_object",
            Params={"Bucket": storage.STORAGE_BUCKET, "Key": chave, "ContentType": content_type},
            ExpiresIn=validade_s,
        )
        return _relativa(url)

    def metadados(self, chave: str) -> MetadadosDoObjeto | None:
        try:
            cabecalho = storage.get_client().head_object(Bucket=storage.STORAGE_BUCKET, Key=chave)
        except ClientError as erro:
            if erro.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return MetadadosDoObjeto(
            tamanho_bytes=int(cabecalho["ContentLength"]), content_type=str(cabecalho.get("ContentType", ""))
        )

    def url_para_ler(self, chave: str, validade_s: int) -> str:
        url = storage.get_client().generate_presigned_url(
            "get_object", Params={"Bucket": storage.STORAGE_BUCKET, "Key": chave}, ExpiresIn=validade_s
        )
        return _relativa(url)

    def apagar(self, chave: str) -> None:
        storage.apagar_objeto(chave)
