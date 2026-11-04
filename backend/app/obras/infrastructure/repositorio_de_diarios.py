"""Repositório SQLAlchemy de diários: o agregado ↔ `diarios`, `ocorrencias`, `diario_fotos`,
`diario_revisoes` e `comentarios`.

Preso a uma empresa (construtor) e, por baixo, à sessão do tenant. Concorrência otimista como
na obra: conteúdo ou status alterado vai com `WHERE versao = <lida>`; 0 linhas → 409. Fotos,
revisões e comentários são linhas novas e não mexem na versão (dois encarregados anexando
fotos ao mesmo tempo não conflitam).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.obras.domain.diario import DiarioDeObra
from app.obras.domain.erros import DiarioDuplicado, DiarioNaoEncontrado, FotoNaoEncontrada
from app.obras.domain.ids import DiarioId, FotoId, ObraId, OcorrenciaId
from app.obras.domain.valores_do_diario import (
    Clima,
    CondicaoDeTrabalho,
    ConteudoDoDiario,
    FotoDoDiario,
    ObjectKey,
    Ocorrencia,
    StatusDiario,
    Tempo,
    TipoOcorrencia,
)
from app.obras.infrastructure.modelos import (
    ComentarioModel,
    DiarioFotoModel,
    DiarioModel,
    DiarioRevisaoModel,
    OcorrenciaModel,
)
from app.shared.domain.erros import ConflitoDeVersao
from app.shared.domain.ids import EmpresaId, UsuarioId

UNICO_POR_DIA = "uq_diarios_obra_data"


def _sem_fuso(momento: datetime | None) -> datetime | None:
    if momento is None or momento.tzinfo is None:
        return momento
    return momento.astimezone(UTC).replace(tzinfo=None)


def _colunas(d: DiarioDeObra) -> dict[str, Any]:
    c = d.conteudo
    return {
        "data": d.data,
        "clima_manha": c.clima.manha.value if c.clima.manha else None,
        "clima_tarde": c.clima.tarde.value if c.clima.tarde else None,
        "condicao": c.condicao.value,
        "atividades": c.atividades,
        "efetivo": c.efetivo,
        "observacoes": c.observacoes,
        "status": d.status.value,
        "publicado_em": _sem_fuso(d.publicado_em),
    }


def _ocorrencias(d: DiarioDeObra) -> dict[OcorrenciaId, Ocorrencia]:
    return {o.id: o for o in d.conteudo.ocorrencias}


def _e_duplicado(erro: IntegrityError) -> bool:
    texto = str(erro.orig)
    # MariaDB cita o nome do índice; o SQLite, as colunas
    return UNICO_POR_DIA in texto or "diarios.obra_id, diarios.data" in texto


Retrato = tuple[dict[str, Any], frozenset[OcorrenciaId], frozenset[FotoId]]


class RepositorioDeDiariosSQL:
    def __init__(self, session: Session, empresa_id: EmpresaId) -> None:
        self._session = session
        self._empresa_id = empresa_id
        self._lidos: dict[DiarioId, Retrato] = {}
        # Agregados desta transação: a unidade de trabalho recolhe os eventos deles no commit
        self.vistos: dict[DiarioId, DiarioDeObra] = {}

    # ── Leitura ───────────────────────────────────────────────────────────────

    def obter(self, diario_id: DiarioId) -> DiarioDeObra:
        modelo = self._session.scalars(
            select(DiarioModel).where(
                DiarioModel.id == diario_id.valor, DiarioModel.empresa_id == self._empresa_id.valor
            )
        ).one_or_none()
        if modelo is None:
            raise DiarioNaoEncontrado()
        return self._montar(modelo)

    def obter_pela_foto(self, foto_id: FotoId) -> DiarioDeObra:
        diario_id = self._session.scalar(
            select(DiarioFotoModel.diario_id).where(
                DiarioFotoModel.id == foto_id.valor, DiarioFotoModel.empresa_id == self._empresa_id.valor
            )
        )
        if diario_id is None:
            raise FotoNaoEncontrada()
        return self.obter(DiarioId(diario_id))

    def existe_na_data(self, obra_id: ObraId, data: date, exceto: DiarioId | None = None) -> bool:
        consulta = select(DiarioModel.id).where(
            DiarioModel.empresa_id == self._empresa_id.valor,
            DiarioModel.obra_id == obra_id.valor,
            DiarioModel.data == data,
        )
        if exceto is not None:
            consulta = consulta.where(DiarioModel.id != exceto.valor)
        return bool(self._session.scalar(select(exists(consulta))))

    def contar_fotos_da_obra(self, obra_id: ObraId) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(DiarioFotoModel)
                .join(
                    DiarioModel,
                    (DiarioModel.id == DiarioFotoModel.diario_id)
                    & (DiarioModel.empresa_id == DiarioFotoModel.empresa_id),
                )
                .where(DiarioModel.empresa_id == self._empresa_id.valor, DiarioModel.obra_id == obra_id.valor)
            )
            or 0
        )

    def _montar(self, m: DiarioModel) -> DiarioDeObra:
        filtro = {"diario_id": m.id, "empresa_id": m.empresa_id}
        ocorrencias = self._session.scalars(
            select(OcorrenciaModel).filter_by(**filtro).order_by(OcorrenciaModel.criado_em, OcorrenciaModel.id)
        ).all()
        fotos = self._session.scalars(
            select(DiarioFotoModel).filter_by(**filtro).order_by(DiarioFotoModel.criado_em, DiarioFotoModel.id)
        ).all()
        diario = DiarioDeObra(
            id=DiarioId(m.id),
            empresa_id=EmpresaId(m.empresa_id),
            obra_id=ObraId(m.obra_id),
            data=m.data,
            conteudo=ConteudoDoDiario(
                clima=Clima(
                    Tempo(m.clima_manha) if m.clima_manha else None, Tempo(m.clima_tarde) if m.clima_tarde else None
                ),
                condicao=CondicaoDeTrabalho(m.condicao),
                atividades=m.atividades,
                efetivo=m.efetivo,
                observacoes=m.observacoes,
                ocorrencias=tuple(
                    Ocorrencia(
                        tipo=TipoOcorrencia(o.tipo),
                        descricao=o.descricao,
                        impacto_prazo_dias=o.impacto_prazo_dias,
                        id=OcorrenciaId(o.id),
                    )
                    for o in ocorrencias
                ),
            ),
            status=StatusDiario(m.status),
            autor_id=UsuarioId(m.autor_id),
            versao=m.versao,
            publicado_em=m.publicado_em,
            fotos=[
                FotoDoDiario(
                    id=FotoId(f.id),
                    object_key=ObjectKey(f.object_key),
                    content_type=f.content_type,
                    tamanho_bytes=f.tamanho_bytes,
                    enviado_por=UsuarioId(f.enviado_por),
                    legenda=f.legenda,
                    criado_em=f.criado_em,
                )
                for f in fotos
            ],
        )
        self._lembrar(diario)
        return diario

    def _lembrar(self, d: DiarioDeObra) -> None:
        self._lidos[d.id] = (_colunas(d), frozenset(_ocorrencias(d)), frozenset(f.id for f in d.fotos))
        self.vistos[d.id] = d

    # ── Escrita ───────────────────────────────────────────────────────────────

    def adicionar(self, diario: DiarioDeObra) -> None:
        if diario.empresa_id != self._empresa_id:
            raise DiarioNaoEncontrado()
        agora = datetime.now(UTC).replace(tzinfo=None)
        self._session.add(
            DiarioModel(
                id=diario.id.valor,
                empresa_id=self._empresa_id.valor,
                obra_id=diario.obra_id.valor,
                autor_id=diario.autor_id.valor,
                versao=diario.versao,
                criado_em=agora,
                atualizado_em=agora,
                **_colunas(diario),
            )
        )
        self._flush()
        self._gravar_filhos(diario, ocorrencias_lidas=frozenset(), fotos_lidas=frozenset())
        self._lembrar(diario)

    def salvar(self, diario: DiarioDeObra) -> None:
        colunas_lidas, ocorrencias_lidas, fotos_lidas = self._lidos.get(diario.id, ({}, frozenset(), frozenset()))
        if diario.removido:
            self._apagar(diario)
            return
        colunas = _colunas(diario)
        if colunas != colunas_lidas or frozenset(_ocorrencias(diario)) != ocorrencias_lidas:
            resultado = self._session.execute(
                update(DiarioModel)
                .where(*self._mesma_versao(diario))
                .values(**colunas, versao=DiarioModel.versao + 1, atualizado_em=func.now())
                .execution_options(synchronize_session=False)
            )
            if resultado.rowcount != 1:
                raise ConflitoDeVersao(versao_atual=self._versao_no_banco(diario.id))
            diario.versao += 1
        self._gravar_filhos(diario, ocorrencias_lidas, fotos_lidas)
        self._lembrar(diario)

    def _gravar_filhos(
        self, d: DiarioDeObra, ocorrencias_lidas: frozenset[OcorrenciaId], fotos_lidas: frozenset[FotoId]
    ) -> None:
        empresa, diario_id = self._empresa_id.valor, d.id.valor
        ocorrencias = _ocorrencias(d)
        if saiu := ocorrencias_lidas - ocorrencias.keys():
            self._session.execute(
                delete(OcorrenciaModel)
                .where(OcorrenciaModel.empresa_id == empresa, OcorrenciaModel.id.in_([i.valor for i in saiu]))
                .execution_options(synchronize_session=False)
            )
        for oid in ocorrencias.keys() - ocorrencias_lidas:
            o = ocorrencias[oid]
            self._session.add(
                OcorrenciaModel(
                    id=oid.valor,
                    empresa_id=empresa,
                    diario_id=diario_id,
                    tipo=o.tipo.value,
                    descricao=o.descricao,
                    impacto_prazo_dias=o.impacto_prazo_dias,
                )
            )
        fotos = {f.id: f for f in d.fotos}
        if saiu_foto := fotos_lidas - fotos.keys():
            self._session.execute(
                delete(DiarioFotoModel)
                .where(DiarioFotoModel.empresa_id == empresa, DiarioFotoModel.id.in_([i.valor for i in saiu_foto]))
                .execution_options(synchronize_session=False)
            )
        for fid in fotos.keys() - fotos_lidas:
            f = fotos[fid]
            self._session.add(
                DiarioFotoModel(
                    id=fid.valor,
                    empresa_id=empresa,
                    diario_id=diario_id,
                    object_key=str(f.object_key),
                    content_type=f.content_type,
                    tamanho_bytes=f.tamanho_bytes,
                    legenda=f.legenda,
                    enviado_por=f.enviado_por.valor,
                    criado_em=_sem_fuso(f.criado_em) or datetime.now(UTC).replace(tzinfo=None),
                )
            )
        for r in d.puxar_revisoes_novas():
            self._session.add(
                DiarioRevisaoModel(
                    id=r.id.valor,
                    empresa_id=empresa,
                    diario_id=diario_id,
                    versao_anterior=r.versao_anterior,
                    snapshot=r.retrato,
                    motivo=r.motivo,
                    autor_id=r.autor_id.valor,
                    criado_em=_sem_fuso(r.criado_em),
                )
            )
        for c in d.puxar_comentarios_novos():
            self._session.add(
                ComentarioModel(
                    id=c.id.valor,
                    empresa_id=empresa,
                    diario_id=diario_id,
                    autor_id=c.autor_id.valor,
                    texto=c.texto,
                    criado_em=_sem_fuso(c.criado_em),
                )
            )
        self._flush()

    def _apagar(self, d: DiarioDeObra) -> None:
        empresa, diario_id = self._empresa_id.valor, d.id.valor
        # Os filhos saem explicitamente: não depende do ON DELETE CASCADE (o SQLite dos testes
        # não liga FK por padrão). Revisões e comentários só existem em publicado, que não sai.
        for modelo in (OcorrenciaModel, DiarioFotoModel):
            self._session.execute(
                delete(modelo)
                .where(modelo.empresa_id == empresa, modelo.diario_id == diario_id)
                .execution_options(synchronize_session=False)
            )
        resultado = self._session.execute(
            delete(DiarioModel).where(*self._mesma_versao(d)).execution_options(synchronize_session=False)
        )
        if resultado.rowcount != 1:
            raise ConflitoDeVersao(versao_atual=self._versao_no_banco(d.id))
        self._lidos.pop(d.id, None)

    def _mesma_versao(self, d: DiarioDeObra) -> tuple[Any, ...]:
        return (
            DiarioModel.id == d.id.valor,
            DiarioModel.empresa_id == self._empresa_id.valor,
            DiarioModel.versao == d.versao,
        )

    def _flush(self) -> None:
        try:
            self._session.flush()
        except IntegrityError as erro:
            if _e_duplicado(erro):
                raise DiarioDuplicado() from None
            raise

    def _versao_no_banco(self, diario_id: DiarioId) -> int | None:
        return self._session.scalar(
            select(DiarioModel.versao).where(
                DiarioModel.id == diario_id.valor, DiarioModel.empresa_id == self._empresa_id.valor
            )
        )
