"""Eventos de domínio da Obra. Viram linhas da outbox (Fase 4b) no formato da Parte A.4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.obras.domain.ids import ObraId
from app.shared.domain.eventos import EventoDeDominio
from app.shared.domain.ids import EmpresaId, UsuarioId

Dados = dict[str, str | int | None]


@dataclass(frozen=True, kw_only=True)
class EventoDaObra(EventoDeDominio):
    recurso: ClassVar[str] = "obra"

    empresa_id: EmpresaId
    ator_id: UsuarioId
    obra_id: ObraId

    @property
    def recurso_id(self) -> str:
        return str(self.obra_id)

    def dados(self) -> Dados:
        return {}


@dataclass(frozen=True, kw_only=True)
class ObraCriada(EventoDaObra):
    tipo: str = "obra.criada"
    nome: str

    def dados(self) -> Dados:
        return {"nome": self.nome}


@dataclass(frozen=True, kw_only=True)
class ObraEditada(EventoDaObra):
    tipo: str = "obra.editada"
    campos: tuple[str, ...]

    def dados(self) -> Dados:
        return {"campos": ",".join(self.campos)}


@dataclass(frozen=True, kw_only=True)
class ObraStatusAlterado(EventoDaObra):
    tipo: str = "obra.status_alterado"
    de: str
    para: str

    def dados(self) -> Dados:
        return {"de": self.de, "para": self.para}


@dataclass(frozen=True, kw_only=True)
class ObraRemovida(EventoDaObra):
    tipo: str = "obra.removida"


@dataclass(frozen=True, kw_only=True)
class MembroAdicionado(EventoDaObra):
    tipo: str = "obra.membro_adicionado"
    usuario_id: UsuarioId
    papel: str

    def dados(self) -> Dados:
        return {"usuario_id": self.usuario_id.valor, "papel": self.papel}


@dataclass(frozen=True, kw_only=True)
class MembroRemovido(EventoDaObra):
    tipo: str = "obra.membro_removido"
    usuario_id: UsuarioId

    def dados(self) -> Dados:
        return {"usuario_id": self.usuario_id.valor}
