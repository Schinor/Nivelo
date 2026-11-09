"""Camada anticorrupção do Stripe: daqui para dentro só existem `Plano`, status e ids nossos.

O cartão é digitado só nas páginas hospedadas pelo Stripe; aqui passam apenas identificadores.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import stripe

from app.assinaturas.domain.assinatura import (
    EVENTO_CHECKOUT_CONCLUIDO,
    EVENTO_PAGAMENTO_FALHOU,
    AssinaturaDoWebhookInvalida,
    AssinaturaNoPagamento,
    EventoDePagamento,
)
from app.assinaturas.domain.planos import StatusAssinatura
from app.shared.application.erros import DependenciaIndisponivel
from app.shared.domain.ids import EmpresaId, UsuarioId

logger = logging.getLogger("nivelo.api.stripe")

Dados = dict[str, Any]


def _id_de(valor: Any) -> str | None:
    """O Stripe manda o id, ou o objeto expandido com o id dentro."""
    if isinstance(valor, dict):
        valor = valor.get("id")
    return str(valor) if valor else None


def _empresa(valor: Any) -> EmpresaId | None:
    try:
        return EmpresaId.de_texto(str(valor)) if valor else None
    except ValueError:
        logger.warning("empresa_id inválido nos metadados do Stripe")
        return None


def _usuario(valor: Any) -> UsuarioId | None:
    return UsuarioId(int(valor)) if str(valor or "").isdigit() and int(valor) > 0 else None


def _assinatura_do_aviso(tipo: str, objeto: Dados) -> str | None:
    if tipo == EVENTO_CHECKOUT_CONCLUIDO:
        return _id_de(objeto.get("subscription"))
    if tipo == EVENTO_PAGAMENTO_FALHOU:
        # Nas versões novas da API a assinatura da fatura mora em parent.subscription_details
        detalhes = (objeto.get("parent") or {}).get("subscription_details") or {}
        return _id_de(objeto.get("subscription") or detalhes.get("subscription"))
    return _id_de(objeto.get("id"))


def evento_de(dados: Dados) -> EventoDePagamento:
    tipo = str(dados.get("type", ""))
    objeto: Dados = (dados.get("data") or {}).get("object") or {}
    referencia = objeto.get("client_reference_id") or (objeto.get("metadata") or {}).get("empresa_id")
    return EventoDePagamento(
        id=str(dados["id"]),
        tipo=tipo,
        subscription_id=_assinatura_do_aviso(tipo, objeto),
        customer_id=_id_de(objeto.get("customer")),
        empresa_id=_empresa(referencia),
    )


def assinatura_de(dados: Dados) -> AssinaturaNoPagamento:
    item: Dados = ((dados.get("items") or {}).get("data") or [{}])[0]
    preco: Dados = item.get("price") or {}
    fim = dados.get("current_period_end") or item.get("current_period_end")
    metadata = dados.get("metadata") or {}
    return AssinaturaNoPagamento(
        subscription_id=str(dados["id"]),
        customer_id=_id_de(dados.get("customer")),
        price_id=_id_de(preco),
        status=StatusAssinatura.de_texto(str(dados.get("status", ""))),
        periodo_fim=datetime.fromtimestamp(int(fim), UTC).replace(tzinfo=None) if fim else None,
        cancelar_no_fim=bool(dados.get("cancel_at_period_end")),
        valor_mensal_centavos=int(preco.get("unit_amount") or 0) * int(item.get("quantity") or 1),
        empresa_id=_empresa(metadata.get("empresa_id")),
        usuario_id=_usuario(metadata.get("usuario_id")),
    )


class StripeGateway:
    def __init__(self, chave: str, segredo_do_webhook: str, url_do_app: str) -> None:
        self._chave = chave
        self._segredo = segredo_do_webhook
        self._url = url_do_app.rstrip("/")

    def criar_customer(self, empresa_id: EmpresaId, email: str | None, nome: str | None) -> str:
        opcionais: Any = {k: v for k, v in (("email", email), ("name", nome)) if v}
        with _traduzindo_erros():
            cliente = stripe.Customer.create(
                api_key=self._chave,
                # Dois cliques seguidos não criam dois clientes para a mesma empresa
                idempotency_key=f"customer-empresa-{empresa_id}",
                metadata={"empresa_id": str(empresa_id)},
                **opcionais,
            )
        return cliente.id

    def criar_checkout_assinatura(
        self, customer_id: str, empresa_id: EmpresaId, usuario_id: UsuarioId, price_id: str
    ) -> str:
        metadata = {"empresa_id": str(empresa_id), "usuario_id": str(usuario_id.valor)}
        with _traduzindo_erros():
            sessao = stripe.checkout.Session.create(
                api_key=self._chave,
                mode="subscription",
                customer=customer_id,
                client_reference_id=str(empresa_id),
                line_items=[{"price": price_id, "quantity": 1}],
                metadata=metadata,
                subscription_data={"metadata": metadata},
                locale="pt-BR",
                success_url=f"{self._url}/assinatura?checkout=sucesso",
                cancel_url=f"{self._url}/assinatura?checkout=cancelado",
            )
        return str(sessao.url)

    def criar_sessao_portal(self, customer_id: str) -> str:
        with _traduzindo_erros():
            sessao = stripe.billing_portal.Session.create(
                api_key=self._chave, customer=customer_id, return_url=f"{self._url}/assinatura"
            )
        return str(sessao.url)

    def buscar_assinatura(self, subscription_id: str) -> AssinaturaNoPagamento:
        with _traduzindo_erros():
            assinatura = stripe.Subscription.retrieve(subscription_id, api_key=self._chave)
        return assinatura_de(assinatura.to_dict_recursive())

    def validar_evento(self, payload: bytes, assinatura: str) -> EventoDePagamento:
        """A assinatura é conferida sobre o corpo bruto, e o JSON é lido dos mesmos bytes."""
        try:
            stripe.Webhook.construct_event(payload, assinatura, self._segredo)  # type: ignore[no-untyped-call]
        except (ValueError, stripe.SignatureVerificationError):
            raise AssinaturaDoWebhookInvalida from None
        return evento_de(json.loads(payload))


class _traduzindo_erros:
    """O resto do sistema não conhece as exceções do SDK."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, _tipo: object, erro: BaseException | None, _rastro: object) -> None:
        if isinstance(erro, stripe.StripeError):
            # A mensagem do Stripe mascara a chave e aponta o campo recusado (preço, URL, customer)
            logger.warning(
                "Stripe recusou a chamada: %s http=%s codigo=%s campo=%s: %s",
                type(erro).__name__,
                erro.http_status,
                erro.code,
                getattr(erro, "param", None),
                erro.user_message,
            )
            raise DependenciaIndisponivel("Não foi possível falar com o meio de pagamento. Tente de novo.") from None
