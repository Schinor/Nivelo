"""Consultas SQLAlchemy de diários (CQRS leve: SELECT direto em DTOs). A sessão já vem presa ao
tenant; a visibilidade por papel é a mesma das obras (`obras_visiveis`), e o cliente só vê
diário publicado."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.obras.application.consultas import (
    ComentarioDTO,
    DiarioDetalhe,
    DiarioResumo,
    FotoDTO,
    OcorrenciaDTO,
    RevisaoDTO,
)
from app.obras.domain.erros import DiarioNaoEncontrado, FotoNaoEncontrada, ObraNaoEncontrada
from app.obras.domain.ids import DiarioId, FotoId, ObraId
from app.obras.infrastructure.consultas import obras_visiveis
from app.obras.infrastructure.modelos import (
    ComentarioModel,
    DiarioFotoModel,
    DiarioModel,
    DiarioRevisaoModel,
    ObraModel,
    OcorrenciaModel,
)
from app.shared.application.contexto import TenantContext
from app.shared.application.paginacao import Pagina, PedidoDePagina


def _contagem(modelo: Any) -> Any:
    return (
        select(func.count())
        .select_from(modelo)
        .where(modelo.diario_id == DiarioModel.id, modelo.empresa_id == DiarioModel.empresa_id)
        .correlate(DiarioModel)
        .scalar_subquery()
    )


class ConsultaDeDiariosSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _visiveis(self, ctx: TenantContext, consulta: Select[Any]) -> Select[Any]:
        consulta = consulta.join(
            ObraModel, (ObraModel.id == DiarioModel.obra_id) & (ObraModel.empresa_id == DiarioModel.empresa_id)
        )
        consulta = obras_visiveis(ctx, consulta).where(DiarioModel.empresa_id == ctx.empresa_id.valor)
        if ctx.papel == "cliente":
            consulta = consulta.where(DiarioModel.status == "publicado")
        return consulta

    def _diario(self, ctx: TenantContext, diario_id: DiarioId) -> DiarioModel:
        d: DiarioModel | None = self._session.scalars(
            self._visiveis(ctx, select(DiarioModel)).where(DiarioModel.id == diario_id.valor)
        ).first()
        if d is None:
            raise DiarioNaoEncontrado()
        return d

    def listar(
        self, ctx: TenantContext, obra_id: ObraId, status: str | None = None, pagina: PedidoDePagina | None = None
    ) -> Pagina[DiarioResumo]:
        pagina = pagina or PedidoDePagina()
        obra_visivel = self._session.scalar(
            obras_visiveis(ctx, select(ObraModel.id)).where(ObraModel.id == obra_id.valor)
        )
        if obra_visivel is None:
            raise ObraNaoEncontrada()
        filtro = self._visiveis(ctx, select(DiarioModel)).where(DiarioModel.obra_id == obra_id.valor)
        if status is not None:
            filtro = filtro.where(DiarioModel.status == status)
        total = self._session.scalar(select(func.count()).select_from(filtro.subquery())) or 0
        consulta = (
            filtro.add_columns(_contagem(DiarioFotoModel), _contagem(OcorrenciaModel))
            .order_by(DiarioModel.data.desc(), DiarioModel.id)
            .offset(pagina.deslocamento)
            .limit(pagina.por_pagina)
        )
        itens = [
            DiarioResumo(
                id=d.id,
                obra_id=d.obra_id,
                data=d.data,
                status=d.status,
                condicao=d.condicao,
                efetivo=d.efetivo,
                autor_id=d.autor_id,
                publicado_em=d.publicado_em,
                fotos=int(fotos or 0),
                ocorrencias=int(ocorrencias or 0),
            )
            for d, fotos, ocorrencias in self._session.execute(consulta)
        ]
        return Pagina(itens=itens, pagina=pagina.pagina, por_pagina=pagina.por_pagina, total=int(total))

    def detalhar(self, ctx: TenantContext, diario_id: DiarioId) -> DiarioDetalhe:
        d = self._diario(ctx, diario_id)
        filtro = {"diario_id": d.id, "empresa_id": d.empresa_id}
        ocorrencias = self._session.scalars(
            select(OcorrenciaModel).filter_by(**filtro).order_by(OcorrenciaModel.criado_em, OcorrenciaModel.id)
        )
        fotos = self._session.scalars(
            select(DiarioFotoModel).filter_by(**filtro).order_by(DiarioFotoModel.criado_em, DiarioFotoModel.id)
        )
        revisoes = self._session.scalar(select(func.count()).select_from(DiarioRevisaoModel).filter_by(**filtro))
        return DiarioDetalhe(
            id=d.id,
            obra_id=d.obra_id,
            data=d.data,
            clima_manha=d.clima_manha,
            clima_tarde=d.clima_tarde,
            condicao=d.condicao,
            atividades=d.atividades,
            efetivo=d.efetivo,
            observacoes=d.observacoes,
            status=d.status,
            autor_id=d.autor_id,
            versao=d.versao,
            publicado_em=d.publicado_em,
            criado_em=d.criado_em,
            atualizado_em=d.atualizado_em,
            ocorrencias=[OcorrenciaDTO(o.id, o.tipo, o.descricao, o.impacto_prazo_dias) for o in ocorrencias],
            fotos=[
                FotoDTO(f.id, f.content_type, f.tamanho_bytes, f.legenda, f.enviado_por, f.criado_em) for f in fotos
            ],
            revisoes=int(revisoes or 0),
        )

    def revisoes(self, ctx: TenantContext, diario_id: DiarioId) -> list[RevisaoDTO]:
        d = self._diario(ctx, diario_id)
        return [
            RevisaoDTO(r.id, r.versao_anterior, r.motivo, r.autor_id, r.criado_em, dict(r.snapshot))
            for r in self._session.scalars(
                select(DiarioRevisaoModel)
                .filter_by(diario_id=d.id, empresa_id=d.empresa_id)
                .order_by(DiarioRevisaoModel.versao_anterior.desc(), DiarioRevisaoModel.criado_em.desc())
            )
        ]

    def comentarios(
        self, ctx: TenantContext, diario_id: DiarioId, pagina: PedidoDePagina | None = None
    ) -> Pagina[ComentarioDTO]:
        pagina = pagina or PedidoDePagina()
        d = self._diario(ctx, diario_id)
        filtro = select(ComentarioModel).filter_by(diario_id=d.id, empresa_id=d.empresa_id)
        total = self._session.scalar(select(func.count()).select_from(filtro.subquery())) or 0
        itens = [
            ComentarioDTO(c.id, c.autor_id, c.texto, c.criado_em)
            for c in self._session.scalars(
                filtro.order_by(ComentarioModel.criado_em, ComentarioModel.id)
                .offset(pagina.deslocamento)
                .limit(pagina.por_pagina)
            )
        ]
        return Pagina(itens=itens, pagina=pagina.pagina, por_pagina=pagina.por_pagina, total=int(total))

    def chave_da_foto(self, ctx: TenantContext, foto_id: FotoId) -> str:
        consulta = (
            select(DiarioFotoModel.object_key)
            .join(
                DiarioModel,
                (DiarioModel.id == DiarioFotoModel.diario_id) & (DiarioModel.empresa_id == DiarioFotoModel.empresa_id),
            )
            .where(DiarioFotoModel.id == foto_id.valor)
        )
        chave = self._session.scalar(self._visiveis(ctx, consulta))
        if chave is None:
            raise FotoNaoEncontrada()
        return str(chave)
