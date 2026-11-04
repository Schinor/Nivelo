"""Agregado DiarioDeObra: o registro de um dia de uma obra (Parte A.3).

É uma raiz separada da Obra: uma obra tem centenas de diários, e carregar todos para
registrar um seria lento e geraria conflito de concorrência.

Invariantes:
- a data não é futura (no fuso do negócio);
- publicar exige as atividades preenchidas;
- **diário publicado não é sobrescrito**: alterar exige um motivo, gera uma
  `RevisaoDoDiario` com o retrato anterior e o evento `DiarioRevisado`;
- diário publicado não é removido, e as fotos dele também não (são prova); anexar foto
  num publicado pode, porque só acrescenta;
- comentário só em diário publicado.

"Um diário por obra por dia" depende dos outros diários da obra: o caso de uso confere no
repositório antes de gravar (`DiarioDuplicado`), e o índice único garante no banco.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from app.obras.domain.erros import (
    ComentarioInvalido,
    DataDoDiarioFutura,
    DiarioJaPublicado,
    DiarioNaoPublicado,
    FotoInvalida,
    FotoNaoEncontrada,
    PublicacaoSemAtividades,
    RevisaoSemMotivo,
    RevisaoSemMudanca,
)
from app.obras.domain.eventos import (
    ComentarioRegistrado,
    DiarioEditado,
    DiarioPublicado,
    DiarioRegistrado,
    DiarioRemovido,
    DiarioRevisado,
    EventoDoDiario,
    FotoAnexada,
    FotoRemovida,
    OcorrenciaRegistrada,
)
from app.obras.domain.ids import ComentarioId, DiarioId, FotoId, ObraId, RevisaoId
from app.obras.domain.valores_do_diario import (
    ConteudoDoDiario,
    FotoDoDiario,
    Ocorrencia,
    RevisaoDoDiario,
    StatusDiario,
)
from app.shared.domain.ids import EmpresaId, UsuarioId

MOTIVO_MIN, MOTIVO_MAX = 5, 500
COMENTARIO_MAX = 2_000


@dataclass(frozen=True, slots=True)
class Comentario:
    id: ComentarioId
    texto: str
    autor_id: UsuarioId
    criado_em: datetime


class DiarioDeObra:
    def __init__(
        self,
        *,
        id: DiarioId,
        empresa_id: EmpresaId,
        obra_id: ObraId,
        data: date,
        conteudo: ConteudoDoDiario,
        status: StatusDiario,
        autor_id: UsuarioId,
        versao: int = 1,
        publicado_em: datetime | None = None,
        fotos: list[FotoDoDiario] | None = None,
    ) -> None:
        """Reconstitui um diário que já existe (o repositório usa). Diário novo: `registrar`."""
        self.id = id
        self.empresa_id = empresa_id
        self.obra_id = obra_id
        self.data = data
        self.conteudo = conteudo
        self.status = status
        self.autor_id = autor_id
        self.versao = versao
        self.publicado_em = publicado_em
        self.removido = False
        self._fotos: dict[FotoId, FotoDoDiario] = {f.id: f for f in fotos or []}
        self._revisoes_novas: list[RevisaoDoDiario] = []
        self._comentarios_novos: list[Comentario] = []
        self._eventos: list[EventoDoDiario] = []

    # ── Fábrica ───────────────────────────────────────────────────────────────

    @classmethod
    def registrar(
        cls,
        *,
        empresa_id: EmpresaId,
        obra_id: ObraId,
        data: date,
        conteudo: ConteudoDoDiario,
        autor: UsuarioId,
        hoje: date,
        id: DiarioId | None = None,
    ) -> DiarioDeObra:
        _exigir_data_valida(data, hoje)
        diario = cls(
            id=id or DiarioId.novo(),
            empresa_id=empresa_id,
            obra_id=obra_id,
            data=data,
            conteudo=conteudo,
            status=StatusDiario.RASCUNHO,
            autor_id=autor,
        )
        diario._registrar(DiarioRegistrado, autor)
        diario._registrar_ocorrencias(conteudo.ocorrencias, autor)
        return diario

    # ── Leitura ───────────────────────────────────────────────────────────────

    @property
    def publicado(self) -> bool:
        return self.status is StatusDiario.PUBLICADO

    @property
    def fotos(self) -> tuple[FotoDoDiario, ...]:
        return tuple(self._fotos.values())

    def foto(self, foto_id: FotoId) -> FotoDoDiario:
        foto = self._fotos.get(foto_id)
        if foto is None:
            raise FotoNaoEncontrada()
        return foto

    def pode_ser_revisado_por(self, ator: UsuarioId, papel: str) -> bool:
        """Dono revisa qualquer diário; encarregado, só os que ele registrou."""
        return papel == "dono" or (papel == "encarregado" and ator == self.autor_id)

    # ── Rascunho ──────────────────────────────────────────────────────────────

    def editar(self, *, conteudo: ConteudoDoDiario, data: date, ator: UsuarioId, hoje: date) -> tuple[str, ...]:
        """Altera o rascunho. Devolve os campos que mudaram (vazio: nada mudou)."""
        if self.publicado:
            raise DiarioJaPublicado("Diário publicado não é sobrescrito: altere por revisão, informando o motivo.")
        _exigir_data_valida(data, hoje)
        campos = self._aplicar(conteudo, data, ator)
        if campos:
            self._registrar(DiarioEditado, ator, campos=campos)
        return campos

    def publicar(self, ator: UsuarioId, quando: datetime) -> None:
        if self.publicado:
            raise DiarioJaPublicado("O diário já está publicado.")
        if not self.conteudo.atividades:
            raise PublicacaoSemAtividades()
        self.status = StatusDiario.PUBLICADO
        self.publicado_em = quando
        self._registrar(DiarioPublicado, ator)

    def remover(self, ator: UsuarioId) -> None:
        if self.publicado:
            raise DiarioJaPublicado("Diário publicado é registro de prova e não pode ser removido.")
        self.removido = True
        self._registrar(DiarioRemovido, ator)

    # ── Publicado ─────────────────────────────────────────────────────────────

    def revisar(
        self,
        *,
        conteudo: ConteudoDoDiario,
        data: date,
        motivo: str | None,
        ator: UsuarioId,
        quando: datetime,
        hoje: date,
    ) -> RevisaoDoDiario:
        """Altera o diário publicado guardando o retrato anterior, com o motivo."""
        if not self.publicado:
            raise DiarioNaoPublicado("Rascunho se edita direto, sem revisão.")
        motivo_limpo = motivo.strip() if isinstance(motivo, str) else ""
        if not MOTIVO_MIN <= len(motivo_limpo) <= MOTIVO_MAX:
            raise RevisaoSemMotivo()
        _exigir_data_valida(data, hoje)
        if not conteudo.atividades:
            raise PublicacaoSemAtividades()
        retrato = {"versao": self.versao, "data": self.data.isoformat(), **self.conteudo.retrato()}
        versao_anterior = self.versao
        campos = self._aplicar(conteudo, data, ator)
        if not campos:
            raise RevisaoSemMudanca()
        revisao = RevisaoDoDiario(
            id=RevisaoId.novo(),
            versao_anterior=versao_anterior,
            retrato=retrato,
            motivo=motivo_limpo,
            autor_id=ator,
            criado_em=quando,
        )
        self._revisoes_novas.append(revisao)
        self._registrar(DiarioRevisado, ator, versao_anterior=versao_anterior, motivo=motivo_limpo, campos=campos)
        return revisao

    def comentar(self, texto: str, autor: UsuarioId, quando: datetime) -> Comentario:
        if not self.publicado:
            raise DiarioNaoPublicado("Só dá para comentar em diário publicado.")
        limpo = texto.strip() if isinstance(texto, str) else ""
        if not limpo:
            raise ComentarioInvalido("Escreva o comentário.")
        if len(limpo) > COMENTARIO_MAX:
            raise ComentarioInvalido(f"O comentário deve ter no máximo {COMENTARIO_MAX} caracteres.")
        comentario = Comentario(id=ComentarioId.novo(), texto=limpo, autor_id=autor, criado_em=quando)
        self._comentarios_novos.append(comentario)
        self._registrar(ComentarioRegistrado, autor, comentario_id=comentario.id)
        return comentario

    # ── Fotos ─────────────────────────────────────────────────────────────────

    def anexar_foto(self, foto: FotoDoDiario, ator: UsuarioId) -> FotoDoDiario:
        """Idempotente: confirmar de novo a mesma foto devolve a que já está anexada."""
        if not foto.object_key.pertence_a(self.empresa_id, self.obra_id, self.id):
            raise FotoInvalida("Essa foto não foi enviada para este diário.")
        if foto.object_key.foto_id != foto.id:
            raise FotoInvalida("Chave de foto inválida.")
        existente = self._fotos.get(foto.id)
        if existente is not None:
            return existente
        self._fotos[foto.id] = foto
        self._registrar(
            FotoAnexada, ator, foto_id=foto.id, object_key=str(foto.object_key), tamanho_bytes=foto.tamanho_bytes
        )
        return foto

    def remover_foto(self, foto_id: FotoId, ator: UsuarioId) -> FotoDoDiario:
        foto = self.foto(foto_id)
        if self.publicado:
            raise DiarioJaPublicado("Foto de diário publicado é prova e não pode ser removida.")
        del self._fotos[foto_id]
        self._registrar(FotoRemovida, ator, foto_id=foto_id)
        return foto

    # ── Para a unidade de trabalho ────────────────────────────────────────────

    def puxar_eventos(self) -> list[EventoDoDiario]:
        eventos, self._eventos = self._eventos, []
        return eventos

    def puxar_revisoes_novas(self) -> list[RevisaoDoDiario]:
        revisoes, self._revisoes_novas = self._revisoes_novas, []
        return revisoes

    def puxar_comentarios_novos(self) -> list[Comentario]:
        comentarios, self._comentarios_novos = self._comentarios_novos, []
        return comentarios

    # ── Interno ───────────────────────────────────────────────────────────────

    def _aplicar(self, conteudo: ConteudoDoDiario, data: date, ator: UsuarioId) -> tuple[str, ...]:
        campos = conteudo.mudancas_em_relacao_a(self.conteudo)
        if data != self.data:
            campos = ("data", *campos)
        if not campos:
            return ()
        conteudo, novas = _manter_ids_das_ocorrencias(self.conteudo, conteudo)
        self.conteudo = conteudo
        self.data = data
        self._registrar_ocorrencias(novas, ator)
        return campos

    def _registrar_ocorrencias(self, ocorrencias: tuple[Ocorrencia, ...], ator: UsuarioId) -> None:
        for o in ocorrencias:
            self._registrar(
                OcorrenciaRegistrada,
                ator,
                ocorrencia_id=o.id,
                tipo_ocorrencia=o.tipo.value,
                impacto_prazo_dias=o.impacto_prazo_dias,
            )

    def _registrar(self, tipo_de_evento: type[EventoDoDiario], ator: UsuarioId, **extras: object) -> None:
        self._eventos.append(
            tipo_de_evento(
                empresa_id=self.empresa_id,
                ator_id=ator,
                diario_id=self.id,
                obra_id=self.obra_id,
                data=self.data,
                **extras,  # type: ignore[arg-type]
            )
        )


def _exigir_data_valida(data: date, hoje: date) -> None:
    if data > hoje:
        raise DataDoDiarioFutura("O diário não pode ser de um dia que ainda não chegou.")


def _manter_ids_das_ocorrencias(
    anterior: ConteudoDoDiario, novo: ConteudoDoDiario
) -> tuple[ConteudoDoDiario, tuple[Ocorrencia, ...]]:
    """Ocorrência com o mesmo conteúdo de uma anterior fica com o id dela; as outras são novas."""
    livres = list(anterior.ocorrencias)
    mantidas: list[Ocorrencia] = []
    novas: list[Ocorrencia] = []
    for o in novo.ocorrencias:
        igual = next((a for a in livres if a == o), None)
        if igual is not None:
            livres.remove(igual)
            mantidas.append(igual)
        else:
            mantidas.append(o)
            novas.append(o)
    return replace(novo, ocorrencias=tuple(mantidas)), tuple(novas)
