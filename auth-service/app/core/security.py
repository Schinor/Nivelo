from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.models.usuario import Usuario

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(Usuario).filter(Usuario.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


class SessaoAtual:
    """Usuário do token e o contexto (empresa ativa e papel) que o token carrega."""

    def __init__(self, usuario, claims: dict) -> None:
        self.usuario = usuario
        self.empresa_id: str | None = claims.get("empresa_id")
        self.papel: str | None = claims.get("papel")


def emitir_token(usuario, vinculo=None) -> str:
    """JWT do Padrão B (ADR 005): sub, nome, email, admin e o contexto do vínculo ativo.

    Sem vínculo (usuário que ainda não tem empresa, ou admin da plataforma), `empresa_id` e
    `papel` vão nulos: é o token sem tenant, que só cria empresa e lista vínculos.
    """
    claims = {
        "sub": str(usuario.id),
        "nome": usuario.nome,
        "email": usuario.email,
        "admin": bool(usuario.admin_plataforma),
        "empresa_id": str(vinculo.empresa_id) if vinculo else None,
        "papel": vinculo.papel if vinculo else None,
        # Legado, sai junto com a coluna antiga de papel (ADR 009)
        "role": usuario.role,
        "permissions": usuario.permissions,
    }
    return create_access_token(claims)


def sessao_atual(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> SessaoAtual:
    usuario = get_current_user(token, db)
    return SessaoAtual(usuario, decode_access_token(token))


def require_permission(permission: str) -> Callable:
    def dependency(current_user=Depends(get_current_user)):
        user_permissions = current_user.permissions_list
        if permission not in user_permissions and "administrar:sistema" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: permissão '{permission}' necessária",
            )
        return current_user

    return dependency
