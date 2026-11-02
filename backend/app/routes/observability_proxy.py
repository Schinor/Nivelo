"""Proxy reverso para Grafana e Prometheus através do ponto de entrada público da API.

Existe porque, em produção (Portainer), o domínio público passa por um proxy
(Cloudflare) que só encaminha um conjunto fixo de portas HTTP — as portas dedicadas
do Grafana/Prometheus (ex: 3220, 9090) nunca chegam a esse proxy. Encaminhando por
aqui, os dois ficam acessíveis pelo mesmo domínio/porta já publicados, seguindo o
mesmo padrão "bridge" usado em app.routes.auth para o auth-service.
"""

import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings

router = APIRouter(tags=["observability"], include_in_schema=False)

# Headers que não devem ser repassados entre proxy e cliente (RFC 7230) — content-encoding
# e content-length também entram aqui porque o httpx já entrega o corpo descomprimido.
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}

_SKIP_REQUEST_HEADERS = {
    b"content-length",
    b"x-forwarded-for",
    b"x-forwarded-proto",
    b"x-forwarded-host",
    *(h.encode() for h in _HOP_BY_HOP_HEADERS),
}

_security = HTTPBasic()


def _require_prometheus_auth(credentials: HTTPBasicCredentials = Depends(_security)) -> None:
    """O Prometheus não tem login próprio, então o proxy exige HTTP Basic (PROMETHEUS_PROXY_PASSWORD)."""
    expected_password = settings.PROMETHEUS_PROXY_PASSWORD
    if not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Proxy do Prometheus não configurado (defina PROMETHEUS_PROXY_PASSWORD)",
        )
    valid_user = secrets.compare_digest(credentials.username, "admin")
    valid_pass = secrets.compare_digest(credentials.password, expected_password)
    if not (valid_user and valid_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )


def _forward_headers(request: Request) -> list[tuple[bytes, bytes]]:
    """Headers repassados ao upstream, como bytes crus.

    - Host é mantido: o Grafana compara Origin com Host na proteção CSRF e recusa
      com 403 ("origin not allowed") os POSTs de consulta dos painéis se o Host
      virar o nome interno do container.
    - Bytes crus porque o Grafana envia headers com acento (X-Panel-Title:
      "Latência p95"), que o httpx não consegue codificar como ASCII a partir de str.
    """
    headers = [
        (key, value)
        for key, value in request.headers.raw
        if key.lower() not in _SKIP_REQUEST_HEADERS
    ]
    # Estende a cadeia que já vier do Cloudflare em vez de duplicar os headers
    client_ip = request.client.host if request.client else ""
    forwarded_for = ", ".join(filter(None, [request.headers.get("x-forwarded-for"), client_ip]))
    headers += [
        (b"x-forwarded-for", forwarded_for.encode("latin-1")),
        (b"x-forwarded-proto", request.headers.get("x-forwarded-proto", request.url.scheme).encode("latin-1")),
        (b"x-forwarded-host", request.headers.get("x-forwarded-host", request.headers.get("host", "")).encode("latin-1")),
    ]
    return headers


async def _proxy_request(request: Request, base_url: str, path: str) -> Response:
    url = f"{base_url.rstrip('/')}/{path}"
    forward_headers = _forward_headers(request)
    body = await request.body()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            upstream = await client.request(
                request.method,
                url,
                params=request.query_params,
                headers=forward_headers,
                content=body,
                follow_redirects=False,
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Serviço de observabilidade indisponível",
            )

    response = Response(content=upstream.content, status_code=upstream.status_code)
    # multi_items + append: um dict juntaria os vários Set-Cookie do Grafana num header só
    for key, value in upstream.headers.multi_items():
        if key.lower() not in _HOP_BY_HOP_HEADERS:
            response.headers.append(key, value)
    return response


@router.get("/grafana")
async def grafana_root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/grafana/")


@router.api_route("/grafana/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_grafana(path: str, request: Request) -> Response:
    """Autenticação é feita pelo próprio Grafana (usuário admin / GRAFANA_ADMIN_PASSWORD)."""
    return await _proxy_request(request, settings.GRAFANA_INTERNAL_URL, path)


@router.get("/prometheus", dependencies=[Depends(_require_prometheus_auth)])
async def prometheus_root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/prometheus/")


@router.api_route(
    "/prometheus/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    dependencies=[Depends(_require_prometheus_auth)],
)
async def proxy_prometheus(path: str, request: Request) -> Response:
    return await _proxy_request(request, settings.PROMETHEUS_INTERNAL_URL, path)
