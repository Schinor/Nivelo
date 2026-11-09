"""A assinatura de uma empresa e como ela acompanha o estado do meio de pagamento."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.assinaturas.domain.planos import DireitosEfetivos, Plano, StatusAssinatura, direitos_efetivos
from app.shared.domain.ids import EmpresaId


@dataclass(frozen=True, slots=True)
class AssinaturaDaEmpresa:
    empresa_id: EmpresaId
    plano: Plano
    status: StatusAssinatura
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    stripe_price_id: str | None
    valor_mensal_centavos: int
    periodo_fim: datetime | None
    cancelar_no_fim: bool

    @property
    def efetivos(self) -> DireitosEfetivos:
        return direitos_efetivos(self.plano, self.status)

    @property
    def tem_assinatura_vigente(self) -> bool:
        """Inclui a inadimplente: ela se resolve no portal, não com uma segunda assinatura."""
        return self.stripe_subscription_id is not None
