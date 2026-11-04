"""Comandos de Gestão de Obras: o que cada caso de uso recebe, já sem nada de HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.obras.domain.ids import DiarioId, FotoId, ObraId
from app.shared.domain.ids import UsuarioId


@dataclass(frozen=True, slots=True)
class DadosDaObra:
    nome: str
    logradouro: str
    cidade: str
    uf: str
    cliente_nome: str
    data_inicio: date
    previsao_termino: date
    latitude: Decimal | None = None
    longitude: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CriarObra:
    dados: DadosDaObra


@dataclass(frozen=True, slots=True)
class EditarObra:
    obra_id: ObraId
    versao_esperada: int
    dados: DadosDaObra


@dataclass(frozen=True, slots=True)
class AlterarStatusObra:
    obra_id: ObraId
    status: str
    versao_esperada: int | None = None


@dataclass(frozen=True, slots=True)
class RemoverObra:
    obra_id: ObraId
    versao_esperada: int | None = None


@dataclass(frozen=True, slots=True)
class AdicionarMembro:
    obra_id: ObraId
    usuario_id: UsuarioId
    papel: str


@dataclass(frozen=True, slots=True)
class RemoverMembro:
    obra_id: ObraId
    usuario_id: UsuarioId


# ── Diário de obra ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DadosDaOcorrencia:
    tipo: str
    descricao: str
    impacto_prazo_dias: int | None = None


@dataclass(frozen=True, slots=True)
class DadosDoDiario:
    data: date
    atividades: str | None = None
    efetivo: int = 0
    condicao: str = "praticavel"
    clima_manha: str | None = None
    clima_tarde: str | None = None
    observacoes: str | None = None
    ocorrencias: tuple[DadosDaOcorrencia, ...] = ()


@dataclass(frozen=True, slots=True)
class RegistrarDiario:
    obra_id: ObraId
    dados: DadosDoDiario


@dataclass(frozen=True, slots=True)
class EditarDiario:
    """Rascunho: edita direto. Publicado: vira revisão e exige `motivo`."""

    diario_id: DiarioId
    versao_esperada: int
    dados: DadosDoDiario
    motivo: str | None = None


@dataclass(frozen=True, slots=True)
class PublicarDiario:
    diario_id: DiarioId
    versao_esperada: int | None = None


@dataclass(frozen=True, slots=True)
class RemoverDiario:
    diario_id: DiarioId
    versao_esperada: int | None = None


@dataclass(frozen=True, slots=True)
class SolicitarUploadFoto:
    diario_id: DiarioId
    content_type: str
    tamanho_bytes: int


@dataclass(frozen=True, slots=True)
class ConfirmarFoto:
    diario_id: DiarioId
    object_key: str
    legenda: str | None = None


@dataclass(frozen=True, slots=True)
class RemoverFoto:
    foto_id: FotoId


@dataclass(frozen=True, slots=True)
class Comentar:
    diario_id: DiarioId
    texto: str
