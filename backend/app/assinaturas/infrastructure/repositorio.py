"""Repositório SQLAlchemy das assinaturas."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assinaturas.domain.assinatura import AssinaturaDaEmpresa
from app.assinaturas.domain.planos import Plano, StatusAssinatura
from app.assinaturas.infrastructure.modelos import AssinaturaModel
from app.shared.domain.ids import EmpresaId
from app.shared.infrastructure.tenancy import definir_tenant


def para_dominio(m: AssinaturaModel) -> AssinaturaDaEmpresa:
    return AssinaturaDaEmpresa(
        empresa_id=EmpresaId(m.empresa_id),
        plano=Plano(m.plano),
        status=StatusAssinatura.de_texto(m.status),
        stripe_customer_id=m.stripe_customer_id,
        stripe_subscription_id=m.stripe_subscription_id,
        stripe_price_id=m.stripe_price_id,
        valor_mensal_centavos=m.valor_mensal_centavos,
        periodo_fim=m.periodo_fim,
        cancelar_no_fim=m.cancelar_no_fim,
    )


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

    def obter(self, empresa_id: EmpresaId) -> AssinaturaDaEmpresa:
        """A assinatura da empresa; a linha Free nasce aqui se ainda não existir."""
        self.garantir_free(empresa_id)
        modelo = self._session.get(AssinaturaModel, empresa_id.valor, populate_existing=True)
        if modelo is None:  # pragma: no cover - a linha acabou de ser gravada
            raise LookupError(f"assinatura da empresa {empresa_id} não encontrada")
        return para_dominio(modelo)

    def guardar_customer(self, empresa_id: EmpresaId, customer_id: str) -> None:
        modelo = self._session.get(AssinaturaModel, empresa_id.valor)
        if modelo is None:  # pragma: no cover - `obter` já garantiu a linha
            raise LookupError(f"assinatura da empresa {empresa_id} não encontrada")
        modelo.stripe_customer_id = customer_id
        self._session.commit()
