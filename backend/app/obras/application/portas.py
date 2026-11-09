"""Portas da aplicação de Gestão de Obras para o que mora fora do contexto."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.assinaturas.application.direitos import ConsultaDireitos
from app.obras.domain.repositorio import RepositorioDeDiarios, RepositorioDeObras
from app.shared.application.unidade_de_trabalho import UnidadeDeTrabalho
from app.shared.domain.ids import UsuarioId


class UnidadeDeTrabalhoDeObras(UnidadeDeTrabalho, Protocol):
    obras: RepositorioDeObras
    diarios: RepositorioDeDiarios
    direitos: ConsultaDireitos


class EquipeDaEmpresa(Protocol):
    """Quem tem vínculo ativo na empresa (Identidade e Acesso, no auth-service)."""

    def papel_de(self, usuario_id: UsuarioId) -> str | None:
        """Papel do vínculo ativo da pessoa na empresa ativa, ou None se ela não faz parte."""
        ...

    def pessoas_que_contam_no_plano(self) -> int:
        """Dono mais encarregados da empresa ativa (clientes não contam no limite do plano)."""
        ...


@dataclass(frozen=True, slots=True)
class MetadadosDoObjeto:
    tamanho_bytes: int
    content_type: str


class ArmazenamentoDeFotos(Protocol):
    """Object storage das fotos (Garage, pela API S3). O navegador envia e baixa direto, por
    URL pré-assinada; a API só assina, confere e apaga."""

    def url_para_enviar(self, chave: str, content_type: str, validade_s: int) -> str:
        """URL de PUT, válida por `validade_s`, que só aceita esse `Content-Type`."""
        ...

    def metadados(self, chave: str) -> MetadadosDoObjeto | None:
        """O `HEAD` do objeto; None se ele não existe."""
        ...

    def url_para_ler(self, chave: str, validade_s: int) -> str: ...

    def apagar(self, chave: str) -> None: ...
