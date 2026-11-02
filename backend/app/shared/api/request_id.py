"""Request ID: liga clique → API → auth-service → evento de auditoria numa linha só.

Lê o `X-Request-ID` de entrada (se for um valor seguro) ou gera um novo, guarda num
ContextVar para os clientes HTTP repassarem e devolve o mesmo valor na resposta.
"""
from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-ID"
_VALIDO = re.compile(r"^[A-Za-z0-9._-]{8,128}$")

request_id_atual: ContextVar[str | None] = ContextVar("request_id_atual", default=None)


def obter_request_id() -> str | None:
    return request_id_atual.get()


class RequestIdMiddleware:
    """Middleware ASGI puro (não bufferiza o corpo, então não atrapalha streaming nem o proxy)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        recebido = dict(scope["headers"]).get(HEADER.lower().encode(), b"").decode("latin-1")
        request_id = recebido if _VALIDO.match(recebido) else str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_atual.set(request_id)

        async def enviar(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                headers = [(k, v) for k, v in mensagem.get("headers", []) if k.lower() != HEADER.lower().encode()]
                headers.append((HEADER.lower().encode(), request_id.encode()))
                mensagem["headers"] = headers
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        finally:
            request_id_atual.reset(token)
