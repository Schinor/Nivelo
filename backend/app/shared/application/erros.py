"""Erros da camada de aplicação (não são regra de negócio, mas a borda os traduz igual)."""

from __future__ import annotations

from app.shared.domain.erros import ErroDeDominio


class DependenciaIndisponivel(ErroDeDominio):
    """Outro serviço necessário para o caso de uso não respondeu (503)."""

    codigo = "servico-indisponivel"
    status = 503
