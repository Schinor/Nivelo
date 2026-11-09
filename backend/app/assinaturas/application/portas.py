"""Portas de Assinaturas: o meio de pagamento e o registro das assinaturas."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.assinaturas.domain.assinatura import AssinaturaDaEmpresa, AssinaturaNoPagamento, EventoDePagamento
from app.assinaturas.domain.eventos import EventoDaAssinatura
from app.shared.domain.ids import EmpresaId, UsuarioId


class GatewayDePagamentos(Protocol):
    def criar_customer(self, empresa_id: EmpresaId, email: str | None, nome: str | None) -> str: ...

    def criar_checkout_assinatura(
        self, customer_id: str, empresa_id: EmpresaId, usuario_id: UsuarioId, price_id: str
    ) -> str: ...

    def criar_sessao_portal(self, customer_id: str) -> str: ...

    def buscar_assinatura(self, subscription_id: str) -> AssinaturaNoPagamento: ...

    def validar_evento(self, payload: bytes, assinatura: str) -> EventoDePagamento: ...


class RegistroDeAssinaturas(Protocol):
    """Usado pelo checkout e pelo portal, com a empresa do token."""

    def obter(self, empresa_id: EmpresaId) -> AssinaturaDaEmpresa: ...

    def guardar_customer(self, empresa_id: EmpresaId, customer_id: str) -> None: ...


class LivroDoWebhook(Protocol):
    """Usado só pelo webhook: não há token, e a empresa vem do evento assinado."""

    def registrar_recebimento(self, event_id: str, tipo: str) -> bool:
        """True se o evento ainda precisa ser processado."""
        ...

    def marcar_processado(self, event_id: str) -> bool:
        """False se outra entrega do mesmo evento já o processou."""
        ...

    def registrar_erro(self, event_id: str, erro: str) -> None: ...

    def empresa_da_assinatura(self, subscription_id: str, customer_id: str | None) -> EmpresaId | None: ...

    def travar(self, empresa_id: EmpresaId) -> AssinaturaDaEmpresa:
        """A assinatura com a linha travada (`FOR UPDATE`); Free em memória se não existir."""
        ...

    def salvar(self, assinatura: AssinaturaDaEmpresa) -> None: ...

    def publicar(self, eventos: Iterable[EventoDaAssinatura]) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
