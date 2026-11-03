"""Erros da API no formato Problem Details (RFC 9457), com `type` estável.

O front trata o erro pelo `type`, não pelo texto. O campo `detail` continua existindo
com a mensagem legível, então quem lia `detail` antes segue funcionando.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.api.request_id import obter_request_id
from app.shared.domain.erros import ErroDeDominio, RecursoNaoEncontrado

logger = logging.getLogger("nivelo.api.erros")

MEDIA_TYPE = "application/problem+json"
BASE_TYPE = "https://nivelo/erros/"

TYPE_POR_STATUS = {
    400: "requisicao-invalida",
    401: "nao-autenticado",
    402: "plano-limite-excedido",
    403: "acesso-negado",
    404: "nao-encontrado",
    409: "conflito",
    413: "conteudo-grande-demais",
    415: "tipo-de-midia-nao-suportado",
    422: "validacao",
    429: "muitas-requisicoes",
    500: "erro-interno",
    502: "servico-externo-falhou",
    503: "servico-indisponivel",
}


def type_para_status(status: int) -> str:
    slug = TYPE_POR_STATUS.get(status)
    return f"{BASE_TYPE}{slug}" if slug else "about:blank"


def problema(
    request: Request,
    status: int,
    detail: str,
    *,
    type_: str | None = None,
    headers: dict[str, str] | None = None,
    **extras: Any,
) -> JSONResponse:
    corpo: dict[str, Any] = {
        "type": type_ or type_para_status(status),
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    request_id = obter_request_id()
    if request_id:
        corpo["request_id"] = request_id
    corpo.update(extras)
    return JSONResponse(status_code=status, content=corpo, media_type=MEDIA_TYPE, headers=headers)


AntesDoProblema = Callable[[Request, StarletteHTTPException], Awaitable[None]]


def registrar_handlers(app: FastAPI, antes_de_http: AntesDoProblema | None = None) -> None:
    """Instala os handlers globais. `antes_de_http` roda antes de responder (ex.: auditar o 403)."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if antes_de_http is not None:
            await antes_de_http(request, exc)
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        return problema(
            request,
            exc.status_code,
            detail,
            type_=getattr(exc, "problem_type", None),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
        erros = [
            {"campo": ".".join(str(p) for p in e.get("loc", ()) if p != "body"), "mensagem": e.get("msg", "")}
            for e in exc.errors()
        ]
        resumo = "; ".join(f"{e['campo']}: {e['mensagem']}" if e["campo"] else e["mensagem"] for e in erros)
        return problema(request, 422, resumo or "Dados inválidos", errors=erros)

    @app.exception_handler(RecursoNaoEncontrado)
    async def nao_encontrado(request: Request, exc: RecursoNaoEncontrado) -> JSONResponse:
        return problema(request, 404, exc.mensagem)

    @app.exception_handler(ErroDeDominio)
    async def regra_de_negocio(request: Request, exc: ErroDeDominio) -> JSONResponse:
        return problema(request, 422, exc.mensagem, type_=f"{BASE_TYPE}{exc.codigo}")

    @app.exception_handler(Exception)
    async def inesperado(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("erro não tratado em %s %s", request.method, request.url.path)
        return problema(request, 500, "Erro interno. Informe o request_id ao suporte.")
