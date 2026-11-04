"""Repositório SQLAlchemy de obras: mapeia o agregado ↔ linhas de `obras` e `obra_membros`.

Preso a uma empresa (construtor) e, por baixo, à sessão do tenant (rede de segurança).
A concorrência é otimista: o UPDATE leva `WHERE versao = <lida>` e, se não afetar linha,
vira `ConflitoDeVersao` (409).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.obras.domain.erros import ObraNaoEncontrada
from app.obras.domain.ids import ObraId
from app.obras.domain.obra import Obra
from app.obras.domain.valores import Endereco, MembroDaObra, PapelDeMembro, Periodo, StatusObra
from app.obras.infrastructure.modelos import ObraMembroModel, ObraModel
from app.shared.domain.erros import ConflitoDeVersao
from app.shared.domain.ids import EmpresaId, UsuarioId


def _sem_fuso(momento: datetime | None) -> datetime | None:
    """O banco guarda UTC sem fuso."""
    if momento is None or momento.tzinfo is None:
        return momento
    return momento.astimezone(UTC).replace(tzinfo=None)


def _decimal(valor: Any) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def _colunas(obra: Obra) -> dict[str, Any]:
    e = obra.endereco
    return {
        "nome": obra.nome,
        "logradouro": e.logradouro,
        "cidade": e.cidade,
        "uf": e.uf,
        "latitude": e.latitude,
        "longitude": e.longitude,
        "cliente_nome": obra.cliente_nome,
        "data_inicio": obra.periodo.inicio,
        "previsao_termino": obra.periodo.previsao_termino,
        "status": obra.status.value,
        "removida_em": _sem_fuso(obra.removida_em),
    }


def _membros(obra: Obra) -> dict[int, str]:
    return {m.usuario_id.valor: m.papel.value for m in obra.membros}


class RepositorioDeObrasSQL:
    def __init__(self, session: Session, empresa_id: EmpresaId) -> None:
        self._session = session
        self._empresa_id = empresa_id
        # Retrato do que foi lido, para gravar só o que mudou
        self._lidos: dict[ObraId, tuple[dict[str, Any], dict[int, str]]] = {}
        # Agregados desta transação: a unidade de trabalho recolhe os eventos deles no commit
        self.vistos: dict[ObraId, Obra] = {}

    def obter(self, obra_id: ObraId) -> Obra:
        modelo = self._session.scalars(
            select(ObraModel).where(
                ObraModel.id == obra_id.valor,
                ObraModel.empresa_id == self._empresa_id.valor,
                ObraModel.removida_em.is_(None),
            )
        ).one_or_none()
        if modelo is None:
            raise ObraNaoEncontrada()
        membros = self._session.scalars(
            select(ObraMembroModel).where(
                ObraMembroModel.obra_id == obra_id.valor, ObraMembroModel.empresa_id == self._empresa_id.valor
            )
        ).all()
        obra = Obra(
            id=obra_id,
            empresa_id=EmpresaId(modelo.empresa_id),
            nome=modelo.nome,
            endereco=Endereco(
                logradouro=modelo.logradouro,
                cidade=modelo.cidade,
                uf=modelo.uf,
                latitude=_decimal(modelo.latitude),
                longitude=_decimal(modelo.longitude),
            ),
            cliente_nome=modelo.cliente_nome,
            periodo=Periodo(modelo.data_inicio, modelo.previsao_termino),
            status=StatusObra(modelo.status),
            criado_por=UsuarioId(modelo.criado_por),
            membros=[MembroDaObra(UsuarioId(m.usuario_id), PapelDeMembro(m.papel), m.adicionado_em) for m in membros],
            versao=modelo.versao,
            removida_em=modelo.removida_em,
        )
        self._lidos[obra_id] = (_colunas(obra), _membros(obra))
        self.vistos[obra_id] = obra
        return obra

    def adicionar(self, obra: Obra) -> None:
        if obra.empresa_id != self._empresa_id:
            raise ObraNaoEncontrada()
        agora = datetime.now(UTC).replace(tzinfo=None)
        self._session.add(
            ObraModel(
                id=obra.id.valor,
                empresa_id=obra.empresa_id.valor,
                criado_por=obra.criado_por.valor,
                versao=obra.versao,
                criado_em=agora,
                atualizado_em=agora,
                **_colunas(obra),
            )
        )
        self._session.flush()
        for usuario_id, papel in _membros(obra).items():
            self._session.add(
                ObraMembroModel(
                    obra_id=obra.id.valor, usuario_id=usuario_id, empresa_id=obra.empresa_id.valor, papel=papel
                )
            )
        self._lidos[obra.id] = (_colunas(obra), _membros(obra))
        self.vistos[obra.id] = obra

    def salvar(self, obra: Obra) -> None:
        colunas_lidas, membros_lidos = self._lidos.get(obra.id, ({}, {}))
        colunas = _colunas(obra)
        if colunas != colunas_lidas:
            resultado = self._session.execute(
                update(ObraModel)
                .where(
                    ObraModel.id == obra.id.valor,
                    ObraModel.empresa_id == self._empresa_id.valor,
                    ObraModel.versao == obra.versao,
                )
                .values(**colunas, versao=ObraModel.versao + 1, atualizado_em=func.now())
                .execution_options(synchronize_session=False)
            )
            if resultado.rowcount != 1:
                raise ConflitoDeVersao(versao_atual=self._versao_no_banco(obra.id))
            obra.versao += 1

        membros = _membros(obra)
        saiu = membros_lidos.keys() - membros.keys()
        if saiu:
            self._session.execute(
                delete(ObraMembroModel)
                .where(
                    ObraMembroModel.obra_id == obra.id.valor,
                    ObraMembroModel.empresa_id == self._empresa_id.valor,
                    ObraMembroModel.usuario_id.in_(saiu),
                )
                .execution_options(synchronize_session=False)
            )
        for usuario_id in membros.keys() - membros_lidos.keys():
            self._session.add(
                ObraMembroModel(
                    obra_id=obra.id.valor,
                    usuario_id=usuario_id,
                    empresa_id=self._empresa_id.valor,
                    papel=membros[usuario_id],
                )
            )
        self._session.flush()
        self._lidos[obra.id] = (colunas, membros)

    def contar_ativas(self) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(ObraModel)
                .where(
                    ObraModel.empresa_id == self._empresa_id.valor,
                    ObraModel.status == StatusObra.ATIVA.value,
                    ObraModel.removida_em.is_(None),
                )
            )
            or 0
        )

    def _versao_no_banco(self, obra_id: ObraId) -> int | None:
        return self._session.scalar(
            select(ObraModel.versao).where(
                ObraModel.id == obra_id.valor, ObraModel.empresa_id == self._empresa_id.valor
            )
        )
