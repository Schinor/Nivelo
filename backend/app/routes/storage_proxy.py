"""Rota /storage/* — ponte entre o navegador e o Garage (sem porta pública).

A API NÃO valida a assinatura: repassa caminho e query exatamente como
chegaram, e o Garage confere assinatura + expiração. Funciona porque a URL foi
assinada com o mesmo host que o httpx envia aqui (garage:3900).

Sem JWT de propósito: <img src> não manda Authorization.
A autenticação do arquivo é a própria assinatura da URL.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.services import storage

router = APIRouter(tags=["storage"], include_in_schema=False)

_CABECALHOS_REPASSADOS = ("content-type", "content-length", "etag", "last-modified")


async def _fechar(resposta: httpx.Response, cliente: httpx.AsyncClient) -> None:
    await resposta.aclose()
    await cliente.aclose()


@router.get(f"{storage.STORAGE_PUBLIC_PREFIX}/{{caminho:path}}")
async def proxy_storage(caminho: str, request: Request):
    # raw_path = caminho ainda codificado, idêntico ao que entrou na assinatura
    # (pela spec ASGI vem sem query, mas alguns servidores/test clients a incluem)
    caminho_bruto = request.scope["raw_path"].decode("latin-1").split("?", 1)[0]
    caminho_upstream = caminho_bruto[len(storage.STORAGE_PUBLIC_PREFIX) :]

    if not caminho_upstream.startswith(f"/{storage.STORAGE_BUCKET}/"):
        raise HTTPException(status_code=404)

    query = request.scope["query_string"].decode("latin-1")
    if "X-Amz-Signature=" not in query:
        raise HTTPException(status_code=403, detail="URL sem assinatura")

    cliente = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        upstream = await cliente.send(
            cliente.build_request("GET", f"{storage.STORAGE_ENDPOINT}{caminho_upstream}?{query}"),
            stream=True,
        )
    except httpx.HTTPError:
        await cliente.aclose()
        raise HTTPException(status_code=502, detail="Storage indisponível")

    cabecalhos = {k: v for k, v in upstream.headers.items() if k.lower() in _CABECALHOS_REPASSADOS}
    if upstream.status_code == 200:
        cabecalhos["cache-control"] = "private, max-age=300"

    # URL expirada/adulterada → 403 do próprio Garage passa direto
    return StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        headers=cabecalhos,
        background=BackgroundTask(_fechar, upstream, cliente),
    )
