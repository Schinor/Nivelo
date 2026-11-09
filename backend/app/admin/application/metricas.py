"""Números do painel da plataforma. Só leitura: junta cobrança, contas e auditoria.

As contas moram no auth-service e os eventos no log-service. Se um deles não responder, o painel
mostra o resto e marca o que faltou com `None`, porque a cobrança vem do banco da própria API.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.assinaturas.domain.planos import Plano, StatusAssinatura
from app.shared.application.erros import DependenciaIndisponivel

ULTIMOS_EVENTOS = 20
_STATUS_INADIMPLENTE = frozenset({StatusAssinatura.PAST_DUE, StatusAssinatura.UNPAID})


@dataclass(frozen=True)
class LinhaDeAssinatura:
    empresa_id: str
    plano: Plano
    status: StatusAssinatura
    valor_mensal_centavos: int


@dataclass(frozen=True)
class EmpresaDaPlataforma:
    id: str
    nome: str
    usuario_ids: frozenset[int]


@dataclass(frozen=True)
class ContasDaPlataforma:
    empresas: Sequence[EmpresaDaPlataforma]
    nomes_de_usuarios: Mapping[int, str]
    total_de_usuarios: int  # sem o admin da plataforma


@dataclass(frozen=True)
class EventoDaPlataforma:
    tipo: str | None
    ator_id: int | None
    ator_papel: str | None
    empresa_id: str | None
    quando: str | None


class LeituraDeAssinaturas(Protocol):
    def linhas(self) -> list[LinhaDeAssinatura]: ...


class LeituraDeContas(Protocol):
    def contas(self) -> ContasDaPlataforma: ...


class LeituraDeEventos(Protocol):
    def ultimos(self, limite: int) -> list[EventoDaPlataforma]: ...


@dataclass(frozen=True)
class Cobranca:
    assinaturas_ativas: int
    mrr_centavos: int
    inadimplentes: int


@dataclass(frozen=True)
class PlanoNoPainel:
    plano: str
    rotulo: str
    empresas: int
    usuarios: int | None


@dataclass(frozen=True)
class EventoNoPainel:
    tipo: str | None
    ator_id: int | None
    ator_nome: str | None
    ator_papel: str | None
    empresa_id: str | None
    empresa_nome: str | None
    quando: str | None


@dataclass(frozen=True)
class MetricasDoPainel:
    empresas_total: int
    usuarios_total: int | None
    por_plano: list[PlanoNoPainel]
    assinaturas_ativas: int
    mrr_centavos: int
    mrr_formatado: str
    inadimplentes: int
    eventos: list[EventoNoPainel] | None


def resumir_cobranca(linhas: Sequence[LinhaDeAssinatura]) -> Cobranca:
    pagas = [linha for linha in linhas if linha.plano is not Plano.FREE]
    ativas = [linha for linha in pagas if linha.status is StatusAssinatura.ACTIVE]
    return Cobranca(
        assinaturas_ativas=len(ativas),
        mrr_centavos=sum(linha.valor_mensal_centavos for linha in ativas),
        inadimplentes=sum(1 for linha in pagas if linha.status in _STATUS_INADIMPLENTE),
    )


def formatar_reais(centavos: int) -> str:
    inteiro, resto = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _por_plano(linhas: Sequence[LinhaDeAssinatura], contas: ContasDaPlataforma | None) -> list[PlanoNoPainel]:
    # A empresa sem linha de assinatura ainda não abriu a tela do plano: ela é Free
    plano_de = {linha.empresa_id: linha.plano for linha in linhas}
    if contas is not None:
        plano_de = {empresa.id: Plano.FREE for empresa in contas.empresas} | plano_de

    resultado = []
    for plano in Plano:
        empresas = {empresa_id for empresa_id, atual in plano_de.items() if atual is plano}
        usuarios: int | None = None
        if contas is not None:
            # Quem trabalha em duas empresas do mesmo plano conta uma vez nesse plano
            usuarios = len({u for empresa in contas.empresas if empresa.id in empresas for u in empresa.usuario_ids})
        resultado.append(PlanoNoPainel(plano.value, plano.rotulo, len(empresas), usuarios))
    return resultado


def _no_painel(evento: EventoDaPlataforma, contas: ContasDaPlataforma | None) -> EventoNoPainel:
    nomes = {} if contas is None else contas.nomes_de_usuarios
    empresas = {} if contas is None else {empresa.id: empresa.nome for empresa in contas.empresas}
    return EventoNoPainel(
        tipo=evento.tipo,
        ator_id=evento.ator_id,
        ator_nome=None if evento.ator_id is None else nomes.get(evento.ator_id),
        ator_papel=evento.ator_papel,
        empresa_id=evento.empresa_id,
        empresa_nome=None if evento.empresa_id is None else empresas.get(evento.empresa_id),
        quando=evento.quando,
    )


def consultar_metricas(
    assinaturas: LeituraDeAssinaturas, contas: LeituraDeContas, eventos: LeituraDeEventos
) -> MetricasDoPainel:
    linhas = assinaturas.linhas()
    cobranca = resumir_cobranca(linhas)
    try:
        dados_das_contas: ContasDaPlataforma | None = contas.contas()
    except DependenciaIndisponivel:
        dados_das_contas = None
    try:
        recentes: list[EventoDaPlataforma] | None = eventos.ultimos(ULTIMOS_EVENTOS)
    except DependenciaIndisponivel:
        recentes = None

    por_plano = _por_plano(linhas, dados_das_contas)
    return MetricasDoPainel(
        empresas_total=sum(item.empresas for item in por_plano),
        usuarios_total=None if dados_das_contas is None else dados_das_contas.total_de_usuarios,
        por_plano=por_plano,
        assinaturas_ativas=cobranca.assinaturas_ativas,
        mrr_centavos=cobranca.mrr_centavos,
        mrr_formatado=formatar_reais(cobranca.mrr_centavos),
        inadimplentes=cobranca.inadimplentes,
        eventos=None if recentes is None else [_no_painel(evento, dados_das_contas) for evento in recentes],
    )
