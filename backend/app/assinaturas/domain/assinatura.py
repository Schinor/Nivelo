"""A assinatura de uma empresa e como ela acompanha o estado do meio de pagamento."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from app.assinaturas.domain.eventos import (
    AssinaturaAlterada,
    AssinaturaCancelada,
    AssinaturaInadimplente,
    AssinaturaIniciada,
    EventoDaAssinatura,
)
from app.assinaturas.domain.planos import (
    STATUS_QUE_DAO_DIREITO,
    DireitosEfetivos,
    Plano,
    StatusAssinatura,
    direitos_efetivos,
)
from app.shared.domain.erros import ErroDeDominio
from app.shared.domain.ids import EmpresaId, UsuarioId

EVENTO_CHECKOUT_CONCLUIDO = "checkout.session.completed"
EVENTO_ASSINATURA_ALTERADA = "customer.subscription.updated"
EVENTO_ASSINATURA_REMOVIDA = "customer.subscription.deleted"
EVENTO_PAGAMENTO_FALHOU = "invoice.payment_failed"
EVENTOS_TRATADOS = frozenset(
    {EVENTO_CHECKOUT_CONCLUIDO, EVENTO_ASSINATURA_ALTERADA, EVENTO_ASSINATURA_REMOVIDA, EVENTO_PAGAMENTO_FALHOU}
)

STATUS_ENCERRADOS = frozenset({StatusAssinatura.CANCELED, StatusAssinatura.INCOMPLETE_EXPIRED})
STATUS_INADIMPLENTES = frozenset({StatusAssinatura.PAST_DUE, StatusAssinatura.UNPAID})


class AssinaturaJaVigente(ErroDeDominio):
    codigo = "assinatura-ja-vigente"
    status = 409


class SemClienteNoPagamento(ErroDeDominio):
    codigo = "sem-assinatura"
    status = 409


class AssinaturaDoWebhookInvalida(Exception):
    """O corpo recebido não foi assinado com o segredo do webhook."""


@dataclass(frozen=True, slots=True)
class PrecosDosPlanos:
    """Liga cada plano pago ao preço do meio de pagamento (vem das variáveis de ambiente)."""

    pro: str
    construtora: str

    def preco_de(self, plano: Plano) -> str:
        return {Plano.PRO: self.pro, Plano.CONSTRUTORA: self.construtora}[plano]

    def plano_de(self, preco: str | None) -> Plano:
        """Preço desconhecido não dá direito a nada: conta como Free."""
        return {self.pro: Plano.PRO, self.construtora: Plano.CONSTRUTORA}.get(preco or "", Plano.FREE)


@dataclass(frozen=True, slots=True)
class AssinaturaNoPagamento:
    """O estado atual da assinatura segundo o meio de pagamento, a fonte da verdade."""

    subscription_id: str
    customer_id: str | None
    price_id: str | None
    status: StatusAssinatura
    periodo_fim: datetime | None
    cancelar_no_fim: bool
    valor_mensal_centavos: int
    empresa_id: EmpresaId | None
    usuario_id: UsuarioId | None


@dataclass(frozen=True, slots=True)
class EventoDePagamento:
    """O aviso recebido no webhook, já sem nada do SDK do meio de pagamento."""

    id: str
    tipo: str
    subscription_id: str | None
    customer_id: str | None
    empresa_id: EmpresaId | None


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

    def com_customer(self, customer_id: str) -> AssinaturaDaEmpresa:
        return replace(self, stripe_customer_id=customer_id)

    def sincronizada_com(self, externa: AssinaturaNoPagamento, precos: PrecosDosPlanos) -> AssinaturaDaEmpresa:
        """Grava o estado atual. Repetir com o mesmo estado dá no mesmo, e por isso eventos
        repetidos ou fora de ordem não mudam o resultado."""
        customer = externa.customer_id or self.stripe_customer_id
        if externa.status in STATUS_ENCERRADOS:
            return replace(
                self,
                plano=Plano.FREE,
                status=StatusAssinatura.CANCELED,
                stripe_customer_id=customer,
                stripe_subscription_id=None,
                stripe_price_id=None,
                valor_mensal_centavos=0,
                periodo_fim=None,
                cancelar_no_fim=False,
            )
        return replace(
            self,
            plano=precos.plano_de(externa.price_id),
            status=externa.status,
            stripe_customer_id=customer,
            stripe_subscription_id=externa.subscription_id,
            stripe_price_id=externa.price_id,
            valor_mensal_centavos=externa.valor_mensal_centavos,
            periodo_fim=externa.periodo_fim,
            cancelar_no_fim=externa.cancelar_no_fim,
        )

    def e_assinatura_antiga(self, externa: AssinaturaNoPagamento) -> bool:
        """Aviso atrasado de uma assinatura encerrada não derruba a que a empresa tem agora."""
        return (
            self.stripe_subscription_id is not None
            and self.stripe_subscription_id != externa.subscription_id
            and externa.status not in STATUS_QUE_DAO_DIREITO
        )


def evento_da_mudanca(
    antes: AssinaturaDaEmpresa, depois: AssinaturaDaEmpresa, tipo_do_aviso: str, ator: UsuarioId
) -> EventoDaAssinatura | None:
    """O que a auditoria registra. Sem mudança de estado não há evento: o checkout concluído
    e a assinatura alterada chegam juntos, e só o primeiro deles muda algo."""

    def evento(classe: Callable[..., EventoDaAssinatura]) -> EventoDaAssinatura:
        return classe(empresa_id=depois.empresa_id, ator_id=ator, plano=depois.plano.value, status=depois.status.value)

    if tipo_do_aviso == EVENTO_PAGAMENTO_FALHOU and depois.status in STATUS_INADIMPLENTES:
        return evento(AssinaturaInadimplente)
    if antes.stripe_subscription_id is not None and depois.stripe_subscription_id is None:
        return evento(AssinaturaCancelada)
    if antes.plano is Plano.FREE and depois.plano is not Plano.FREE:
        return evento(AssinaturaIniciada)
    if (antes.plano, antes.status, antes.cancelar_no_fim) != (depois.plano, depois.status, depois.cancelar_no_fim):
        return evento(AssinaturaAlterada)
    return None
