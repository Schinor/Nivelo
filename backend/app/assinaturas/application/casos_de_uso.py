"""Assinar e gerenciar o plano. O plano em si só muda pelo webhook."""

from __future__ import annotations

from app.assinaturas.application.portas import GatewayDePagamentos, RegistroDeAssinaturas
from app.assinaturas.domain.assinatura import AssinaturaJaVigente, PrecosDosPlanos, SemClienteNoPagamento
from app.assinaturas.domain.planos import Plano
from app.shared.application.contexto import TenantContext
from app.shared.domain.ids import UsuarioId


def iniciar_checkout(
    plano: Plano,
    ctx: TenantContext,
    email: str | None,
    nome: str | None,
    registro: RegistroDeAssinaturas,
    gateway: GatewayDePagamentos,
    precos: PrecosDosPlanos,
) -> str:
    assinatura = registro.obter(ctx.empresa_id)
    if assinatura.tem_assinatura_vigente:
        raise AssinaturaJaVigente(
            "A empresa já tem uma assinatura. Troque de plano ou cancele em Gerenciar assinatura."
        )
    customer = assinatura.stripe_customer_id
    if customer is None:
        customer = gateway.criar_customer(ctx.empresa_id, email, nome)
        registro.guardar_customer(ctx.empresa_id, customer)
    return gateway.criar_checkout_assinatura(
        customer, ctx.empresa_id, UsuarioId(ctx.usuario_id), precos.preco_de(plano)
    )


def abrir_portal(ctx: TenantContext, registro: RegistroDeAssinaturas, gateway: GatewayDePagamentos) -> str:
    customer = registro.obter(ctx.empresa_id).stripe_customer_id
    if customer is None:
        raise SemClienteNoPagamento("A empresa ainda não assinou nenhum plano.")
    return gateway.criar_sessao_portal(customer)
