"""Empresas, vínculos e o vínculo ativo do login."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.empresa import Empresa, Vinculo


def vinculos_ativos(db: Session, usuario_id: int) -> list[Vinculo]:
    """Vínculos ativos do usuário, do mais recente para o mais antigo."""
    consulta = (
        select(Vinculo)
        .where(Vinculo.usuario_id == usuario_id, Vinculo.ativo.is_(True))
        .order_by(Vinculo.criado_em.desc())
    )
    return list(db.scalars(consulta).unique())


def vinculo(db: Session, usuario_id: int, empresa_id: uuid.UUID) -> Vinculo | None:
    return db.get(Vinculo, (usuario_id, empresa_id))


def vinculo_para_login(db: Session, usuario_id: int) -> Vinculo | None:
    """Com vários vínculos, o login escolhe o mais recente (a troca é por /empresa-ativa)."""
    ativos = vinculos_ativos(db, usuario_id)
    return ativos[0] if ativos else None


def documento_em_uso(db: Session, documento: str) -> bool:
    return db.scalar(select(Empresa.id).where(Empresa.documento == documento)) is not None


def criar_empresa_com_dono(db: Session, usuario_id: int, nome: str, tipo_pessoa: str, documento: str | None) -> Vinculo:
    """Cria a empresa e o vínculo `dono` na transação corrente (quem chama faz o commit)."""
    empresa = Empresa(nome=nome, tipo_pessoa=tipo_pessoa, documento=documento)
    db.add(empresa)
    db.flush()
    novo = Vinculo(usuario_id=usuario_id, empresa_id=empresa.id, papel="dono", empresa=empresa)
    db.add(novo)
    db.flush()
    return novo
