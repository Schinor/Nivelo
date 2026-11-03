"""Porta que os outros contextos usam para saber o que o plano da empresa permite."""

from __future__ import annotations

from typing import Protocol

from app.assinaturas.domain.planos import DireitosEfetivos
from app.shared.domain.ids import EmpresaId


class ConsultaDireitos(Protocol):
    def travar_e_obter(self, empresa_id: EmpresaId) -> DireitosEfetivos:
        """Direitos efetivos da empresa, travando a linha da assinatura (`SELECT ... FOR UPDATE`)
        na transação corrente. Duas requisições simultâneas da mesma empresa ficam em fila até
        o commit, então contar e inserir depois disso não passa do limite."""
        ...
