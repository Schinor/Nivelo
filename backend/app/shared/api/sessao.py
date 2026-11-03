"""Sessão do banco já presa à empresa ativa do token (rede de segurança do ORM)."""

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.shared.api.autenticacao import tenant
from app.shared.application.contexto import TenantContext
from app.shared.infrastructure.tenancy import definir_tenant


def sessao_do_tenant(ctx: TenantContext = Depends(tenant), db: Session = Depends(get_db)) -> Iterator[Session]:
    definir_tenant(db, ctx.empresa_id.valor)
    yield db
