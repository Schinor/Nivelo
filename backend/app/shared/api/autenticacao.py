"""Quem está chamando a API, a partir do JWT (Padrão B, ADR 005), e as regras de acesso.

- `identidade`: qualquer token válido, inclusive sem tenant (usuário ainda sem empresa).
- `tenant`: exige empresa ativa no token; sem ela, 403. O `empresa_id` vem só daqui.
- `requer_papel("dono", ...)`: exige um dos papéis do vínculo ativo; senão, 403.
- `requer_admin`: só o admin da plataforma.

Todo 403 daqui é anotado para a auditoria registrar `acesso.negado` (ver app.main).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings
from app.shared.application.contexto import PAPEIS_DE_NEGOCIO, TenantContext
from app.shared.domain.ids import EmpresaId

TYPE_SEM_EMPRESA = "https://nivelo/erros/sem-empresa-ativa"


class AcessoNegado(HTTPException):
    """403 com `type` próprio no Problem Details e contexto para a auditoria."""

    def __init__(self, detail: str, problem_type: str | None = None) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        self.problem_type = problem_type


@dataclass(frozen=True, slots=True)
class Identidade:
    usuario_id: int
    nome: str
    email: str
    admin: bool
    empresa_id: EmpresaId | None
    papel: str | None

    def como_dict(self) -> dict[str, Any]:
        """Formato usado pelas rotas herdadas (`user["id"]`)."""
        return {
            "id": self.usuario_id,
            "nome": self.nome,
            "email": self.email,
            "admin": self.admin,
            "empresa_id": str(self.empresa_id) if self.empresa_id else None,
            "papel": self.papel,
        }


def _nao_autenticado(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def decodificar(token: str) -> Identidade:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        usuario_id = int(claims["sub"])
        empresa = claims.get("empresa_id")
        papel = claims.get("papel")
        empresa_id = EmpresaId.de_texto(empresa) if empresa else None
    except (JWTError, KeyError, TypeError, ValueError):
        raise _nao_autenticado("Token inválido ou expirado") from None
    if papel is not None and papel not in PAPEIS_DE_NEGOCIO:
        raise _nao_autenticado("Token inválido ou expirado")
    if (empresa_id is None) != (papel is None):
        raise _nao_autenticado("Token inválido ou expirado")
    return Identidade(
        usuario_id=usuario_id,
        nome=str(claims.get("nome", "")),
        email=str(claims.get("email", "")),
        admin=bool(claims.get("admin", False)),
        empresa_id=empresa_id,
        papel=papel,
    )


def token_do_cabecalho(authorization: str | None) -> str | None:
    if not authorization:
        return None
    esquema, _, valor = authorization.partition(" ")
    return valor.strip() if esquema.lower() == "bearer" and valor.strip() else None


async def identidade(request: Request, authorization: str | None = Header(default=None)) -> Identidade:
    token = token_do_cabecalho(authorization)
    if token is None:
        raise _nao_autenticado("Token não enviado")
    ident = decodificar(token)
    request.state.identidade = ident
    return ident


def negar(
    request: Request, ident: Identidade | None, recurso: str, detail: str, problem_type: str | None = None
) -> AcessoNegado:
    """Monta o 403 e anota quem/o quê para a auditoria (registrada pelo handler global de 403)."""
    request.state.acesso_negado = {
        "usuario_id": ident.usuario_id if ident else None,
        "empresa_id": str(ident.empresa_id) if ident and ident.empresa_id else None,
        "recurso": recurso,
    }
    return AcessoNegado(detail, problem_type)


async def tenant(request: Request, ident: Identidade = Depends(identidade)) -> TenantContext:
    """Empresa ativa do token. Sem ela (usuário sem vínculo ou admin), 403."""
    if ident.empresa_id is None or ident.papel is None:
        raise negar(
            request,
            ident,
            f"{request.method} {request.url.path}",
            "Escolha ou crie uma empresa para continuar (POST /api/auth/empresas).",
            TYPE_SEM_EMPRESA,
        )
    return TenantContext(empresa_id=ident.empresa_id, usuario_id=ident.usuario_id, papel=ident.papel)


def requer_papel(*papeis: str) -> Callable[..., Awaitable[TenantContext]]:
    desconhecidos = set(papeis) - PAPEIS_DE_NEGOCIO
    if not papeis or desconhecidos:
        raise ValueError(f"papéis inválidos: {sorted(desconhecidos) or 'nenhum'}")

    async def dependencia(
        request: Request, ctx: TenantContext = Depends(tenant), ident: Identidade = Depends(identidade)
    ) -> TenantContext:
        if ctx.papel not in papeis:
            raise negar(
                request,
                ident,
                f"{request.method} {request.url.path}",
                f"Ação permitida só para: {', '.join(papeis)}",
            )
        return ctx

    return dependencia


async def requer_admin(request: Request, ident: Identidade = Depends(identidade)) -> Identidade:
    if not ident.admin:
        raise negar(request, ident, f"{request.method} {request.url.path}", "Acesso restrito ao admin da plataforma")
    return ident
