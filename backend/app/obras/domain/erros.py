"""Erros de domínio de Gestão de Obras. O `codigo` vira o final do `type` do Problem Details."""

from __future__ import annotations

from app.shared.domain.erros import ErroDeDominio, RecursoNaoEncontrado


class ObraNaoEncontrada(RecursoNaoEncontrado):
    """Não existe, é de outra empresa, foi removida ou quem pede não é membro (404 nos quatro)."""

    def __init__(self) -> None:
        super().__init__("Obra não encontrada")


class DadoDaObraInvalido(ErroDeDominio):
    codigo = "obra-dado-invalido"


class PeriodoInvalido(ErroDeDominio):
    codigo = "obra-periodo-invalido"


class TransicaoDeStatusInvalida(ErroDeDominio):
    codigo = "obra-transicao-de-status-invalida"


class MembroInvalido(ErroDeDominio):
    codigo = "obra-membro-invalido"


class MembroDuplicado(ErroDeDominio):
    codigo = "obra-membro-duplicado"
    status = 409


class MembroNaoEncontrado(RecursoNaoEncontrado):
    def __init__(self) -> None:
        super().__init__("Essa pessoa não é membro da obra")


# ── Diário de obra ───────────────────────────────────────────────────────────


class DiarioNaoEncontrado(RecursoNaoEncontrado):
    """Não existe, é de outra empresa, é de obra sem acesso, ou é rascunho e quem pede é o
    cliente (404 em todos)."""

    def __init__(self) -> None:
        super().__init__("Diário não encontrado")


class FotoNaoEncontrada(RecursoNaoEncontrado):
    def __init__(self) -> None:
        super().__init__("Foto não encontrada")


class DadoDoDiarioInvalido(ErroDeDominio):
    codigo = "diario-dado-invalido"


class DataDoDiarioFutura(ErroDeDominio):
    codigo = "diario-data-futura"


class DiarioDuplicado(ErroDeDominio):
    codigo = "diario-duplicado"
    status = 409

    def __init__(self) -> None:
        super().__init__("Já existe um diário desta obra nesse dia. Abra o diário existente para editar.")


class PublicacaoSemAtividades(ErroDeDominio):
    codigo = "diario-publicar-sem-atividades"

    def __init__(self) -> None:
        super().__init__("Descreva as atividades do dia antes de publicar o diário.")


class DiarioJaPublicado(ErroDeDominio):
    """A ação só vale para rascunho (editar sem motivo, publicar de novo, remover)."""

    codigo = "diario-ja-publicado"
    status = 409


class DiarioNaoPublicado(ErroDeDominio):
    """A ação só vale para diário publicado (revisar, comentar)."""

    codigo = "diario-nao-publicado"
    status = 409


class RevisaoSemMotivo(ErroDeDominio):
    codigo = "diario-revisao-sem-motivo"

    def __init__(self) -> None:
        super().__init__("Diário publicado não é sobrescrito: informe o motivo da alteração (de 5 a 500 caracteres).")


class RevisaoSemMudanca(ErroDeDominio):
    codigo = "diario-revisao-sem-mudanca"

    def __init__(self) -> None:
        super().__init__("Nada mudou no diário: a revisão não foi registrada.")


class RevisaoNaoPermitida(ErroDeDominio):
    """Encarregado só revisa os diários publicados que ele mesmo escreveu (403)."""

    codigo = "acesso-negado"
    status = 403

    def __init__(self) -> None:
        super().__init__("O encarregado só revisa os diários que ele mesmo registrou.")


class FotoInvalida(ErroDeDominio):
    codigo = "foto-invalida"


class ComentarioInvalido(ErroDeDominio):
    codigo = "comentario-invalido"
