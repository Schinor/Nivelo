"""Rota /storage/* — ponte entre o navegador e o Garage (sem porta pública).

A API NÃO valida a assinatura: repassa caminho e query exatamente como
chegaram, e o Garage confere assinatura + expiração. Funciona porque a URL foi
assinada com o mesmo host que o httpx envia aqui (garage:3900).

Sem JWT de propósito: <img src> não manda Authorization.
A autenticação do arquivo é a própria assinatura da URL.

A ponte não tem credencial própria: não usa o cliente S3 nem as chaves da API, e não repassa
o Authorization do navegador. Só repassa a requisição que a API já assinou, com o caminho
byte a byte. A assinatura SigV4 cobre o caminho (bucket + chave), então trocar a empresa, a
obra ou o diário na chave invalida a URL, e o Garage responde 403. A validação de prefixo pela
empresa do token acontece antes, na API, quando ela assina (`ObjectKey.para_foto`). Testado
contra o Garage de verdade em scripts/verificar_ponte_storage.py (passo do CI).

PUT: o envio das fotos do diário (URL pré-assinada de 5 min, gerada pela API). Só vale para
chaves sob `empresas/` e com no máximo 5 MB; o Garage confere a assinatura e o Content-Type.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.obras.domain.valores_do_diario import TAMANHO_MAXIMO_FOTO
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


def _caminho_e_query(request: Request) -> tuple[str, str]:
    caminho_bruto = request.scope["raw_path"].decode("latin-1").split("?", 1)[0]
    return caminho_bruto[len(storage.STORAGE_PUBLIC_PREFIX) :], request.scope["query_string"].decode("latin-1")


@router.put(f"{storage.STORAGE_PUBLIC_PREFIX}/{{caminho:path}}")
async def proxy_storage_envio(caminho: str, request: Request):
    caminho_upstream, query = _caminho_e_query(request)
    if not caminho_upstream.startswith(f"/{storage.STORAGE_BUCKET}/empresas/"):
        raise HTTPException(status_code=404)
    if "X-Amz-Signature=" not in query:
        raise HTTPException(status_code=403, detail="URL sem assinatura")
    tamanho = request.headers.get("content-length")
    if tamanho is None or not tamanho.isdigit():
        raise HTTPException(status_code=411, detail="Envie o Content-Length")
    if int(tamanho) > TAMANHO_MAXIMO_FOTO:
        raise HTTPException(status_code=413, detail="A foto precisa ter até 5 MB")

    corpo = bytearray()
    async for pedaco in request.stream():
        corpo.extend(pedaco)
        if len(corpo) > TAMANHO_MAXIMO_FOTO:
            raise HTTPException(status_code=413, detail="A foto precisa ter até 5 MB")

    cabecalhos = {"content-length": str(len(corpo))}
    if "content-type" in request.headers:
        cabecalhos["content-type"] = request.headers["content-type"]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as cliente:
            upstream = await cliente.put(
                f"{storage.STORAGE_ENDPOINT}{caminho_upstream}?{query}", content=bytes(corpo), headers=cabecalhos
            )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Storage indisponível")
    # Assinatura inválida, expirada ou Content-Type diferente do assinado → 403 do Garage
    resposta = {k: v for k, v in upstream.headers.items() if k.lower() in ("etag", "content-type")}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=resposta)
