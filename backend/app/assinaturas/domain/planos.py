"""Planos, direitos e a política que decide se uma ação cabe no plano (Parte A.7).

Os planos são definidos aqui, em código; o Stripe só guarda os preços. Os direitos do plano
pago só valem com a assinatura `active` ou `trialing`: em qualquer outro status a empresa
recebe os direitos do Free, para o Pro não continuar de graça.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.shared.domain.erros import ErroDeDominio


class Plano(StrEnum):
    FREE = "free"
    PRO = "pro"
    CONSTRUTORA = "construtora"

    @property
    def rotulo(self) -> str:
        return {"free": "Free", "pro": "Pro", "construtora": "Construtora"}[self.value]


class StatusAssinatura(StrEnum):
    """Os status de assinatura do Stripe."""

    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"

    @classmethod
    def de_texto(cls, texto: str) -> StatusAssinatura:
        """Status desconhecido conta como não pago (cai no Free), nunca como ativo."""
        try:
            return cls(texto)
        except ValueError:
            return cls.INCOMPLETE


STATUS_QUE_DAO_DIREITO = frozenset({StatusAssinatura.ACTIVE, StatusAssinatura.TRIALING})

ILIMITADO = None  # limite None = sem limite


@dataclass(frozen=True, slots=True)
class Direitos:
    max_obras_ativas: int | None
    max_fotos_por_obra: int | None
    max_membros_equipe: int | None  # dono + encarregados
    logo_no_relatorio: bool


DIREITOS_DO_PLANO: dict[Plano, Direitos] = {
    Plano.FREE: Direitos(max_obras_ativas=1, max_fotos_por_obra=30, max_membros_equipe=2, logo_no_relatorio=False),
    Plano.PRO: Direitos(
        max_obras_ativas=ILIMITADO, max_fotos_por_obra=ILIMITADO, max_membros_equipe=5, logo_no_relatorio=False
    ),
    Plano.CONSTRUTORA: Direitos(
        max_obras_ativas=ILIMITADO,
        max_fotos_por_obra=ILIMITADO,
        max_membros_equipe=ILIMITADO,
        logo_no_relatorio=True,
    ),
}

PROXIMO_PLANO: dict[Plano, Plano | None] = {
    Plano.FREE: Plano.PRO,
    Plano.PRO: Plano.CONSTRUTORA,
    Plano.CONSTRUTORA: None,
}


@dataclass(frozen=True, slots=True)
class DireitosEfetivos:
    """O plano que vale agora (o contratado, ou o Free se o pagamento não está em dia)."""

    plano: Plano
    direitos: Direitos


def direitos_efetivos(plano: Plano, status: StatusAssinatura) -> DireitosEfetivos:
    efetivo = plano if status in STATUS_QUE_DAO_DIREITO else Plano.FREE
    return DireitosEfetivos(plano=efetivo, direitos=DIREITOS_DO_PLANO[efetivo])


class LimiteDoPlanoExcedido(ErroDeDominio):
    """A ação passaria do limite do plano: 402 com o limite, o uso e o plano sugerido."""

    codigo = "plano-limite-excedido"
    status = 402

    def __init__(self, *, mensagem: str, limite: int, atual: int, plano_atual: Plano, plano_sugerido: Plano | None):
        super().__init__(mensagem)
        self.titulo = f"Limite do plano {plano_atual.rotulo} atingido"
        self.limite = limite
        self.atual = atual
        self.plano_atual = plano_atual
        self.plano_sugerido = plano_sugerido

    def extras(self) -> dict[str, object]:
        return {
            "limite": self.limite,
            "atual": self.atual,
            "plano_atual": self.plano_atual.value,
            "plano_sugerido": self.plano_sugerido.value if self.plano_sugerido else None,
            "acao": "/assinatura",
        }


def _no_plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


class PoliticaDePlano:
    """Recebe os direitos efetivos e a contagem atual; deixa passar ou levanta
    `LimiteDoPlanoExcedido`. Quem chama conta dentro da transação que trava a assinatura."""

    @staticmethod
    def exigir_vaga_de_obra_ativa(efetivos: DireitosEfetivos, obras_ativas: int) -> None:
        limite = efetivos.direitos.max_obras_ativas
        if limite is None or obras_ativas < limite:
            return
        sugerido = PROXIMO_PLANO[efetivos.plano]
        convite = f", ou assine o {sugerido.rotulo} para ter obras ilimitadas" if sugerido else ""
        raise LimiteDoPlanoExcedido(
            mensagem=(
                f"O plano {efetivos.plano.rotulo} permite {_no_plural(limite, 'obra ativa', 'obras ativas')}"
                f" e você já tem {obras_ativas}. Conclua ou pause uma obra{convite}."
            ),
            limite=limite,
            atual=obras_ativas,
            plano_atual=efetivos.plano,
            plano_sugerido=sugerido,
        )

    @staticmethod
    def exigir_vaga_de_foto(efetivos: DireitosEfetivos, fotos_na_obra: int) -> None:
        limite = efetivos.direitos.max_fotos_por_obra
        if limite is None or fotos_na_obra < limite:
            return
        sugerido = PROXIMO_PLANO[efetivos.plano]
        convite = f" Assine o {sugerido.rotulo} para ter fotos ilimitadas." if sugerido else ""
        raise LimiteDoPlanoExcedido(
            mensagem=(
                f"O plano {efetivos.plano.rotulo} permite {_no_plural(limite, 'foto', 'fotos')} por obra"
                f" e esta obra já tem {fotos_na_obra}.{convite}"
            ),
            limite=limite,
            atual=fotos_na_obra,
            plano_atual=efetivos.plano,
            plano_sugerido=sugerido,
        )

    @staticmethod
    def exigir_vaga_na_equipe(efetivos: DireitosEfetivos, pessoas_na_equipe: int) -> None:
        """A equipe que conta no plano é o dono mais os encarregados; clientes nunca contam."""
        limite = efetivos.direitos.max_membros_equipe
        if limite is None or pessoas_na_equipe < limite:
            return
        sugerido = PROXIMO_PLANO[efetivos.plano]
        convite = f" Assine o {sugerido.rotulo} para ter uma equipe maior." if sugerido else ""
        raise LimiteDoPlanoExcedido(
            mensagem=(
                f"O plano {efetivos.plano.rotulo} permite {_no_plural(limite, 'pessoa', 'pessoas')} na equipe"
                f" (dono e encarregados) e a sua já tem {pessoas_na_equipe}.{convite}"
            ),
            limite=limite,
            atual=pessoas_na_equipe,
            plano_atual=efetivos.plano,
            plano_sugerido=sugerido,
        )
