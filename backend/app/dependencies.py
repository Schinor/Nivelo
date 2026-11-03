"""Dependências das rotas herdadas, apoiadas em app.shared.api.autenticacao.

As rotas novas usam direto `identidade`, `tenant`, `requer_papel` e `requer_admin`.
"""

from fastapi import Depends, HTTPException, Request

from .clients import log_client
from .shared.api.autenticacao import (
    Identidade,
    decodificar,
    identidade,
    negar,
    requer_admin,
    tenant,
    token_do_cabecalho,
)
from .shared.application.contexto import TenantContext


async def current_user(ident: Identidade = Depends(identidade)) -> dict:
    """Qualquer token válido, inclusive sem tenant (logout, /me)."""
    return ident.como_dict()


async def usuario_com_empresa(_ctx: TenantContext = Depends(tenant), ident: Identidade = Depends(identidade)) -> dict:
    """Exige empresa ativa no token: o token sem tenant recebe 403."""
    return ident.como_dict()


async def exigir_admin(ident: Identidade = Depends(requer_admin)) -> dict:
    return ident.como_dict()


def negar_acesso(request: Request, usuario_id: int | None, recurso: str, detail: str) -> HTTPException:
    """Compatível com as rotas herdadas: monta o 403 e anota para a auditoria."""
    ident = getattr(request.state, "identidade", None)
    erro = negar(request, ident, recurso, detail)
    request.state.acesso_negado["usuario_id"] = usuario_id
    return erro


async def auditar_acesso_negado(request: Request) -> None:
    contexto = getattr(request.state, "acesso_negado", None) or {}
    usuario_id = contexto.get("usuario_id")
    empresa_id = contexto.get("empresa_id")
    if usuario_id is None:
        # 403 sem contexto (ex.: repassado do auth-service): identifica pelo JWT, se houver
        token = token_do_cabecalho(request.headers.get("authorization"))
        if token:
            try:
                ident = decodificar(token)
                usuario_id = ident.usuario_id
                empresa_id = str(ident.empresa_id) if ident.empresa_id else None
            except Exception:
                pass
    await log_client.registrar(
        "acesso.negado",
        request,
        usuario_id=usuario_id,
        recurso=contexto.get("recurso"),
        detalhes=f"{request.method} {request.url.path}",
        empresa_id=empresa_id,
    )
