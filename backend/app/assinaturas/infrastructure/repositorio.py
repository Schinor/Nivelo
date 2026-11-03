"""Repositório SQLAlchemy das assinaturas."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assinaturas.infrastructure.modelos import AssinaturaModel
from app.shared.domain.ids import EmpresaId
from app.shared.infrastructure.tenancy import definir_tenant


class RepositorioDeAssinaturasSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def garantir_free(self, empresa_id: EmpresaId) -> bool:
        # A empresa acabou de nascer: a sessão fica presa a ela, e a rede de segurança confere
        definir_tenant(self._session, empresa_id.valor)
        if self._session.get(AssinaturaModel, empresa_id.valor) is not None:
            return False
        self._session.add(AssinaturaModel(empresa_id=empresa_id.valor, plano="free", status="active"))
        try:
            self._session.commit()
        except IntegrityError:
            # Duas requisições para a mesma empresa: a outra já criou
            self._session.rollback()
            return False
        return True
