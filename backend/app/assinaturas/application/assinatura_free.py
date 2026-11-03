"""Toda empresa nasce no plano Free (Fase 3). Os direitos e limites chegam na Fase 8."""

from __future__ import annotations

from typing import Protocol

from app.shared.domain.ids import EmpresaId


class RepositorioDeAssinaturas(Protocol):
    def garantir_free(self, empresa_id: EmpresaId) -> bool:
        """Cria a assinatura Free se a empresa ainda não tem nenhuma. Devolve True se criou."""
        ...


def garantir_assinatura_free(repositorio: RepositorioDeAssinaturas, empresa_id: EmpresaId) -> bool:
    """Idempotente: chamar de novo (reenvio, empresa já assinante) não muda nada."""
    return repositorio.garantir_free(empresa_id)
