from typing import Callable, Optional
from fastapi import Header, Depends, HTTPException, Request, status
from .clients import log_client
from .clients.auth_client import get_authenticated_user
from .core.security import decode_token


async def current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não enviado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Tenta decodificação rápida local de JWT com validação da assinatura
    token_str = authorization.replace("Bearer ", "").replace("bearer ", "").strip()
    try:
        payload = decode_token(token_str)
        user_id = payload.get("sub")
        if user_id:
            return {
                "id": int(user_id),
                "nome": payload.get("nome", ""),
                "email": payload.get("email", ""),
                "role": payload.get("role", "cliente"),
                "permissions": payload.get("permissions", []),
            }
    except Exception:
        pass

    # Fallback para consulta remota ao microsserviço de autenticação
    return await get_authenticated_user(authorization)


def negar_acesso(request: Request, usuario_id: Optional[int], recurso: str, detail: str) -> HTTPException:
    """Monta o 403 e anota quem/o quê para a auditoria.

    Quem registra o evento 'acesso_negado' é o handler global de 403 (app.main),
    que vale para TODA resposta 403 da API — inclusive as repassadas do auth-service.
    """
    request.state.acesso_negado = {"usuario_id": usuario_id, "recurso": recurso}
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _usuario_id_do_token(request: Request) -> Optional[int]:
    authorization = request.headers.get("authorization") or ""
    try:
        sub = decode_token(authorization.replace("Bearer ", "").replace("bearer ", "").strip()).get("sub")
        return int(sub) if sub else None
    except Exception:
        return None


async def auditar_acesso_negado(request: Request) -> None:
    contexto = getattr(request.state, "acesso_negado", None) or {}
    usuario_id = contexto.get("usuario_id")
    if usuario_id is None:
        # 403 sem contexto (ex.: repassado do auth-service): identifica pelo JWT, se houver
        usuario_id = _usuario_id_do_token(request)
    await log_client.registrar(
        "acesso_negado",
        request,
        usuario_id=usuario_id,
        recurso=contexto.get("recurso"),
        detalhes=f"{request.method} {request.url.path}",
    )


def require_permission(permission: str) -> Callable:
    async def dependency(request: Request, user: dict = Depends(current_user)) -> dict:
        user_permissions = user.get("permissions", [])
        # Acesso permitido se possuir a permissão requerida ou a permissão suprema de admin
        if (
            permission not in user_permissions
            and "administrar:sistema" not in user_permissions
        ):
            raise negar_acesso(
                request,
                user.get("id"),
                permission,
                f"Acesso negado: permissão '{permission}' necessária",
            )
        return user
    return dependency
