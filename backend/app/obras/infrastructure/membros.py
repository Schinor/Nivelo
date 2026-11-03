"""Membros de obra: gravados pela API quando um convite com obra é aceito."""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.obras.infrastructure.modelos import ObraMembroModel, ObraModel
from app.shared.infrastructure.tenancy import definir_tenant

PAPEIS_DE_MEMBRO = ("encarregado", "cliente")


def obra_existe(session: Session, obra_id: uuid.UUID) -> bool:
    """Na sessão do tenant: obra de outra empresa (ou removida) não existe."""
    obra = session.get(ObraModel, obra_id)
    return obra is not None and obra.removida_em is None


def adicionar_membro(session: Session, empresa_id: uuid.UUID, obra_id: uuid.UUID, usuario_id: int, papel: str) -> bool:
    """Idempotente. Devolve True se adicionou. Papel fora de encarregado/cliente não vira membro
    (o dono enxerga todas as obras da empresa sem precisar ser membro)."""
    if papel not in PAPEIS_DE_MEMBRO:
        return False
    definir_tenant(session, empresa_id)
    if not obra_existe(session, obra_id):
        return False
    if session.get(ObraMembroModel, (obra_id, usuario_id)) is not None:
        return False
    session.add(ObraMembroModel(obra_id=obra_id, usuario_id=usuario_id, empresa_id=empresa_id, papel=papel))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return False
    return True
