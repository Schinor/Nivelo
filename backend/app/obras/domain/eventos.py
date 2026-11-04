"""Eventos de domínio de Gestão de Obras. Viram linhas da outbox no formato da Parte A.4."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from app.obras.domain.ids import ComentarioId, DiarioId, FotoId, ObraId, OcorrenciaId
from app.shared.domain.eventos import Dados, EventoDeNegocio
from app.shared.domain.ids import UsuarioId


@dataclass(frozen=True, kw_only=True)
class EventoDaObra(EventoDeNegocio):
    recurso: ClassVar[str] = "obra"

    obra_id: ObraId

    @property
    def recurso_id(self) -> str:
        return str(self.obra_id)


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


# ── Diário de obra ───────────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class EventoDoDiario(EventoDeNegocio):
    """Todo evento do diário leva a obra e a data, para o histórico da obra filtrar."""

    recurso: ClassVar[str] = "diario"

    diario_id: DiarioId
    obra_id: ObraId
    data: date

    @property
    def recurso_id(self) -> str:
        return str(self.diario_id)

    def dados(self) -> Dados:
        return {"obra_id": str(self.obra_id), "diario_id": str(self.diario_id), "data": self.data.isoformat()}


@dataclass(frozen=True, kw_only=True)
class DiarioRegistrado(EventoDoDiario):
    tipo: str = "diario.registrado"


@dataclass(frozen=True, kw_only=True)
class DiarioEditado(EventoDoDiario):
    """Rascunho alterado (o publicado muda por revisão: `DiarioRevisado`)."""

    tipo: str = "diario.editado"
    campos: tuple[str, ...]

    def dados(self) -> Dados:
        return {**super().dados(), "campos": ",".join(self.campos)}


@dataclass(frozen=True, kw_only=True)
class DiarioPublicado(EventoDoDiario):
    tipo: str = "diario.publicado"


@dataclass(frozen=True, kw_only=True)
class DiarioRevisado(EventoDoDiario):
    tipo: str = "diario.revisado"
    versao_anterior: int
    motivo: str
    campos: tuple[str, ...]

    def dados(self) -> Dados:
        return {
            **super().dados(),
            "versao_anterior": self.versao_anterior,
            "motivo": self.motivo,
            "campos": ",".join(self.campos),
        }


@dataclass(frozen=True, kw_only=True)
class DiarioRemovido(EventoDoDiario):
    tipo: str = "diario.removido"


@dataclass(frozen=True, kw_only=True)
class OcorrenciaRegistrada(EventoDoDiario):
    tipo: str = "ocorrencia.registrada"
    ocorrencia_id: OcorrenciaId
    tipo_ocorrencia: str
    impacto_prazo_dias: int | None

    def dados(self) -> Dados:
        return {
            **super().dados(),
            "ocorrencia_id": str(self.ocorrencia_id),
            "tipo": self.tipo_ocorrencia,
            "impacto_prazo_dias": self.impacto_prazo_dias,
        }


@dataclass(frozen=True, kw_only=True)
class FotoAnexada(EventoDoDiario):
    recurso: ClassVar[str] = "foto"
    tipo: str = "foto.anexada"
    foto_id: FotoId
    object_key: str
    tamanho_bytes: int

    @property
    def recurso_id(self) -> str:
        return str(self.foto_id)

    def dados(self) -> Dados:
        return {**super().dados(), "object_key": self.object_key, "tamanho_bytes": self.tamanho_bytes}


@dataclass(frozen=True, kw_only=True)
class FotoRemovida(EventoDoDiario):
    recurso: ClassVar[str] = "foto"
    tipo: str = "foto.removida"
    foto_id: FotoId

    @property
    def recurso_id(self) -> str:
        return str(self.foto_id)


@dataclass(frozen=True, kw_only=True)
class ComentarioRegistrado(EventoDoDiario):
    recurso: ClassVar[str] = "comentario"
    tipo: str = "comentario.registrado"
    comentario_id: ComentarioId

    @property
    def recurso_id(self) -> str:
        return str(self.comentario_id)
