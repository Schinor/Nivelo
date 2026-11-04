"""Value objects do Diário de Obra: imutáveis, comparados por valor e validados no construtor."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.obras.domain.erros import DadoDoDiarioInvalido, FotoInvalida
from app.obras.domain.ids import DiarioId, FotoId, ObraId, OcorrenciaId, RevisaoId
from app.shared.domain.ids import EmpresaId, UsuarioId

MAX_ATIVIDADES = 10_000
MAX_OBSERVACOES = 5_000
MAX_DESCRICAO_OCORRENCIA = 2_000
MAX_EFETIVO = 10_000
MAX_IMPACTO_DIAS = 365
MAX_LEGENDA = 280


class StatusDiario(StrEnum):
    RASCUNHO = "rascunho"
    PUBLICADO = "publicado"


class CondicaoDeTrabalho(StrEnum):
    PRATICAVEL = "praticavel"
    IMPRATICAVEL = "impraticavel"

    @classmethod
    def de_texto(cls, texto: str) -> CondicaoDeTrabalho:
        try:
            return cls(texto)
        except ValueError:
            raise DadoDoDiarioInvalido("A condição de trabalho é praticavel ou impraticavel.") from None


class Tempo(StrEnum):
    """Como estava o tempo num turno."""

    ENSOLARADO = "ensolarado"
    NUBLADO = "nublado"
    CHUVOSO = "chuvoso"
    TEMPESTADE = "tempestade"

    @classmethod
    def de_texto(cls, texto: str) -> Tempo:
        try:
            return cls(texto)
        except ValueError:
            opcoes = ", ".join(t.value for t in cls)
            raise DadoDoDiarioInvalido(f"Clima inválido: {texto!r}. Use {opcoes}.") from None


@dataclass(frozen=True, slots=True)
class Clima:
    """O tempo de manhã e à tarde. Um turno sem registro fica None."""

    manha: Tempo | None = None
    tarde: Tempo | None = None


class TipoOcorrencia(StrEnum):
    CHUVA = "chuva"
    FALTA_DE_MATERIAL = "falta_de_material"
    PEDIDO_DO_CLIENTE = "pedido_do_cliente"
    ACIDENTE = "acidente"
    OUTRO = "outro"

    @classmethod
    def de_texto(cls, texto: str) -> TipoOcorrencia:
        try:
            return cls(texto)
        except ValueError:
            opcoes = ", ".join(t.value for t in cls)
            raise DadoDoDiarioInvalido(f"Tipo de ocorrência inválido: {texto!r}. Use {opcoes}.") from None


def _texto(valor: str | None, campo: str, maximo: int, obrigatorio: bool = False) -> str | None:
    limpo = valor.strip() if isinstance(valor, str) else ""
    if not limpo:
        if obrigatorio:
            raise DadoDoDiarioInvalido(f"Informe {campo}.")
        return None
    if len(limpo) > maximo:
        raise DadoDoDiarioInvalido(f"{campo.capitalize()} deve ter no máximo {maximo} caracteres.")
    return limpo


@dataclass(frozen=True, slots=True)
class Ocorrencia:
    """Fato que afeta a obra. Duas ocorrências com o mesmo conteúdo são a mesma ocorrência na
    edição (o `id` não entra na comparação): editar o diário sem mexer nela mantém o id."""

    tipo: TipoOcorrencia
    descricao: str
    impacto_prazo_dias: int | None = None
    id: OcorrenciaId = field(default_factory=OcorrenciaId.novo, compare=False)

    def __post_init__(self) -> None:
        descricao = _texto(self.descricao, "a descrição da ocorrência", MAX_DESCRICAO_OCORRENCIA, obrigatorio=True)
        object.__setattr__(self, "descricao", descricao)
        impacto = self.impacto_prazo_dias
        if impacto is not None and (isinstance(impacto, bool) or not 0 <= impacto <= MAX_IMPACTO_DIAS):
            raise DadoDoDiarioInvalido(f"O impacto no prazo vai de 0 a {MAX_IMPACTO_DIAS} dias.")


@dataclass(frozen=True, slots=True)
class ConteudoDoDiario:
    """O que se escreve no diário. É o que a revisão retrata antes de mudar."""

    clima: Clima = field(default_factory=Clima)
    condicao: CondicaoDeTrabalho = CondicaoDeTrabalho.PRATICAVEL
    atividades: str | None = None
    efetivo: int = 0
    observacoes: str | None = None
    ocorrencias: tuple[Ocorrencia, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "atividades", _texto(self.atividades, "as atividades", MAX_ATIVIDADES))
        object.__setattr__(self, "observacoes", _texto(self.observacoes, "as observações", MAX_OBSERVACOES))
        if isinstance(self.efetivo, bool) or not 0 <= self.efetivo <= MAX_EFETIVO:
            raise DadoDoDiarioInvalido(f"O efetivo vai de 0 a {MAX_EFETIVO} pessoas.")
        object.__setattr__(self, "ocorrencias", tuple(self.ocorrencias))

    def mudancas_em_relacao_a(self, anterior: ConteudoDoDiario) -> tuple[str, ...]:
        """Nomes dos campos que mudaram (as ocorrências comparam pelo conteúdo, não pelo id)."""
        campos = ("clima", "condicao", "atividades", "efetivo", "observacoes")
        mudou = tuple(c for c in campos if getattr(self, c) != getattr(anterior, c))
        if sorted(map(_chave, self.ocorrencias)) != sorted(map(_chave, anterior.ocorrencias)):
            mudou += ("ocorrencias",)
        return mudou

    def retrato(self) -> dict[str, object]:
        """Retrato serializável (JSON) do conteúdo, guardado na revisão."""
        return {
            "clima_manha": self.clima.manha.value if self.clima.manha else None,
            "clima_tarde": self.clima.tarde.value if self.clima.tarde else None,
            "condicao": self.condicao.value,
            "atividades": self.atividades,
            "efetivo": self.efetivo,
            "observacoes": self.observacoes,
            "ocorrencias": [
                {
                    "id": str(o.id),
                    "tipo": o.tipo.value,
                    "descricao": o.descricao,
                    "impacto_prazo_dias": o.impacto_prazo_dias,
                }
                for o in self.ocorrencias
            ],
        }


def _chave(o: Ocorrencia) -> tuple[str, str, int]:
    return (o.tipo.value, o.descricao, -1 if o.impacto_prazo_dias is None else o.impacto_prazo_dias)


# ── Fotos ────────────────────────────────────────────────────────────────────

TAMANHO_MAXIMO_FOTO = 5 * 1024 * 1024
EXTENSAO_DO_TIPO = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
TIPO_DA_EXTENSAO = {v: k for k, v in EXTENSAO_DO_TIPO.items()}


def exigir_imagem_aceita(content_type: str, tamanho_bytes: int) -> None:
    if content_type not in EXTENSAO_DO_TIPO:
        raise FotoInvalida("A foto precisa ser JPEG, PNG ou WebP.")
    if isinstance(tamanho_bytes, bool) or not 0 < tamanho_bytes <= TAMANHO_MAXIMO_FOTO:
        raise FotoInvalida("A foto precisa ter até 5 MB. Reduza a imagem e tente de novo.")


_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_FORMATO_DA_CHAVE = re.compile(
    rf"^empresas/(?P<empresa>{_UUID})/obras/(?P<obra>{_UUID})/diarios/(?P<diario>{_UUID})"
    rf"/(?P<foto>{_UUID})\.(?P<ext>jpg|png|webp)$"
)


@dataclass(frozen=True, slots=True)
class ObjectKey:
    """Chave da foto no bucket:
    `empresas/{empresa_id}/obras/{obra_id}/diarios/{diario_id}/{foto_id}.{jpg|png|webp}`.

    A chave diz a quem a foto pertence; a confirmação do upload confere que ela é do diário
    em que está sendo anexada, para ninguém anexar o objeto de outra empresa."""

    valor: str

    def __post_init__(self) -> None:
        if not isinstance(self.valor, str) or _FORMATO_DA_CHAVE.match(self.valor) is None:
            raise FotoInvalida("Chave de foto inválida.")

    @classmethod
    def para_foto(
        cls, empresa_id: EmpresaId, obra_id: ObraId, diario_id: DiarioId, foto_id: FotoId, content_type: str
    ) -> ObjectKey:
        extensao = EXTENSAO_DO_TIPO.get(content_type)
        if extensao is None:
            raise FotoInvalida("A foto precisa ser JPEG, PNG ou WebP.")
        return cls(f"empresas/{empresa_id}/obras/{obra_id}/diarios/{diario_id}/{foto_id}.{extensao}")

    def _partes(self) -> re.Match[str]:
        partes = _FORMATO_DA_CHAVE.match(self.valor)
        assert partes is not None  # validado no construtor
        return partes

    @property
    def foto_id(self) -> FotoId:
        return FotoId(uuid.UUID(self._partes()["foto"]))

    @property
    def content_type(self) -> str:
        return TIPO_DA_EXTENSAO[self._partes()["ext"]]

    def pertence_a(self, empresa_id: EmpresaId, obra_id: ObraId, diario_id: DiarioId) -> bool:
        p = self._partes()
        return (p["empresa"], p["obra"], p["diario"]) == (str(empresa_id), str(obra_id), str(diario_id))

    def __str__(self) -> str:
        return self.valor


@dataclass(frozen=True, slots=True)
class FotoDoDiario:
    id: FotoId
    object_key: ObjectKey
    content_type: str
    tamanho_bytes: int
    enviado_por: UsuarioId
    legenda: str | None = None
    criado_em: datetime | None = None

    def __post_init__(self) -> None:
        exigir_imagem_aceita(self.content_type, self.tamanho_bytes)
        if self.object_key.content_type != self.content_type:
            raise FotoInvalida("O tipo da foto não bate com a extensão do arquivo.")
        legenda = self.legenda.strip() if isinstance(self.legenda, str) else ""
        if len(legenda) > MAX_LEGENDA:
            raise FotoInvalida(f"A legenda deve ter no máximo {MAX_LEGENDA} caracteres.")
        object.__setattr__(self, "legenda", legenda or None)


@dataclass(frozen=True, slots=True)
class RevisaoDoDiario:
    """O retrato do diário publicado antes de uma alteração, com o motivo e quem alterou."""

    id: RevisaoId
    versao_anterior: int
    retrato: dict[str, object]
    motivo: str
    autor_id: UsuarioId
    criado_em: datetime
