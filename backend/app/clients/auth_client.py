import os
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.shared.api.request_id import HEADER as REQUEST_ID_HEADER
from app.shared.api.request_id import obter_request_id

AUTH_SERVICE_URL = getattr(
    settings, "AUTH_SERVICE_URL", os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
).rstrip("/")


async def forward_request(
    method: str,
    path: str,
    json_data: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    interno: bool = False,
) -> Any:
    url = f"{AUTH_SERVICE_URL}{path}"
    req_headers = {}
    if headers and "authorization" in headers:
        req_headers["authorization"] = headers["authorization"]
    if interno:
        # Rotas /internal do auth-service (ex.: gravar o status premium vindo do webhook do Stripe)
        req_headers["X-Internal-Token"] = settings.AUTH_INTERNAL_TOKEN
    request_id = obter_request_id()
    if request_id:
        req_headers[REQUEST_ID_HEADER] = request_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.request(
                method=method,
                url=url,
                json=json_data,
                data=data,
                headers=req_headers,
            )
            if resp.status_code >= 400:
                try:
                    err_json = resp.json()
                    detail = err_json.get("detail", err_json.get("message", "Erro no auth-service"))
                except Exception:
                    detail = resp.text or "Erro no auth-service"
                raise HTTPException(status_code=resp.status_code, detail=detail)
            if resp.status_code == status.HTTP_204_NO_CONTENT or not resp.content:
                return None
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail="Erro no auth-service")
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Serviço de autenticação inacessível: {str(exc)}",
            )


async def get_authenticated_user(authorization: str | None) -> dict[str, Any]:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não enviado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await forward_request("GET", "/me", headers={"authorization": authorization})


async def usuario_premium(usuario_id: int) -> bool:
    """Status premium lido do BANCO (via auth-service), nunca da claim do JWT, que pode estar velha."""
    usuario = await forward_request("GET", f"/users/{usuario_id}")
    return bool(usuario.get("premium"))
