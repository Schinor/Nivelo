"""Value objects da Obra: imutáveis, comparados por valor e validados no construtor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from app.obras.domain.erros import DadoDaObraInvalido, MembroInvalido, PeriodoInvalido
from app.shared.domain.ids import UsuarioId

UFS = frozenset("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


def texto_obrigatorio(valor: str, campo: str, maximo: int) -> str:
    """Tira os espaços das pontas e exige de 1 a `maximo` caracteres."""
    limpo = valor.strip() if isinstance(valor, str) else ""
    if not limpo:
        raise DadoDaObraInvalido(f"Informe {campo}.")
    if len(limpo) > maximo:
        raise DadoDaObraInvalido(f"{campo.capitalize()} deve ter no máximo {maximo} caracteres.")
    return limpo


@dataclass(frozen=True, slots=True)
class Endereco:
    logradouro: str
    cidade: str
    uf: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "logradouro", texto_obrigatorio(self.logradouro, "o logradouro", 200))
        object.__setattr__(self, "cidade", texto_obrigatorio(self.cidade, "a cidade", 120))
        uf = self.uf.strip().upper() if isinstance(self.uf, str) else ""
        if uf not in UFS:
            raise DadoDaObraInvalido(f"UF inválida: {self.uf!r}. Use a sigla do estado, como SP.")
        object.__setattr__(self, "uf", uf)
        if (self.latitude is None) != (self.longitude is None):
            raise DadoDaObraInvalido("Informe latitude e longitude juntas, ou nenhuma das duas.")
        if self.latitude is not None and not Decimal(-90) <= self.latitude <= Decimal(90):
            raise DadoDaObraInvalido("Latitude deve estar entre -90 e 90.")
        if self.longitude is not None and not Decimal(-180) <= self.longitude <= Decimal(180):
            raise DadoDaObraInvalido("Longitude deve estar entre -180 e 180.")


@dataclass(frozen=True, slots=True)
class Periodo:
    """Início da obra e previsão de término. A previsão nunca é antes do início."""

    inicio: date
    previsao_termino: date

    def __post_init__(self) -> None:
        if self.previsao_termino < self.inicio:
            raise PeriodoInvalido("A previsão de término não pode ser antes do início da obra.")


class StatusObra(StrEnum):
    ATIVA = "ativa"
    PAUSADA = "pausada"
    CONCLUIDA = "concluida"

    def pode_ir_para(self, novo: StatusObra) -> bool:
        """ativa ↔ pausada; ativa ou pausada → concluida; concluida é final."""
        return novo in _TRANSICOES[self]


_TRANSICOES: dict[StatusObra, frozenset[StatusObra]] = {
    StatusObra.ATIVA: frozenset({StatusObra.PAUSADA, StatusObra.CONCLUIDA}),
    StatusObra.PAUSADA: frozenset({StatusObra.ATIVA, StatusObra.CONCLUIDA}),
    StatusObra.CONCLUIDA: frozenset(),
}


class PapelDeMembro(StrEnum):
    """Papel de quem entra numa obra. O dono não é membro: ele enxerga todas as obras."""

    ENCARREGADO = "encarregado"
    CLIENTE = "cliente"

    @classmethod
    def de_texto(cls, texto: str) -> PapelDeMembro:
        try:
            return cls(texto)
        except ValueError:
            raise MembroInvalido("O membro da obra só pode ser encarregado ou cliente.") from None


@dataclass(frozen=True, slots=True)
class MembroDaObra:
    usuario_id: UsuarioId
    papel: PapelDeMembro
    adicionado_em: datetime | None = None
