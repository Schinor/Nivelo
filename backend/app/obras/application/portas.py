"""Portas da aplicação de Gestão de Obras para o que mora fora do contexto."""

from __future__ import annotations

from typing import Protocol

from app.assinaturas.application.direitos import ConsultaDireitos
from app.obras.domain.repositorio import RepositorioDeObras
from app.shared.application.unidade_de_trabalho import UnidadeDeTrabalho
from app.shared.domain.ids import UsuarioId


class UnidadeDeTrabalhoDeObras(UnidadeDeTrabalho, Protocol):
    obras: RepositorioDeObras
    direitos: ConsultaDireitos


class EquipeDaEmpresa(Protocol):
    """Quem tem vínculo ativo na empresa (Identidade e Acesso, no auth-service)."""

    def papel_de(self, usuario_id: UsuarioId) -> str | None:
        """Papel do vínculo ativo da pessoa na empresa ativa, ou None se ela não faz parte."""
        ...
