"""Convites pela API: o dono convida para um papel e, se quiser, para uma obra da empresa.

A API confere a obra (contexto de Obras) e repassa ao auth-service, dono dos convites e dos
vínculos. No aceite, o auth-service cria a conta e o vínculo; a API grava o membro da obra.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.assinaturas.domain.planos import PoliticaDePlano
from app.clients.auth_client import forward_request
from app.core.database import get_db
from app.obras.api.dependencias import equipe_da_empresa
from app.obras.application.portas import EquipeDaEmpresa
from app.obras.infrastructure.membros import adicionar_membro, obra_existe
from app.schemas.convite import AceiteIn, AceiteOut, ConviteIn, ConviteOut
from app.shared.api.autenticacao import requer_papel
from app.shared.api.sessao import sessao_do_tenant
from app.shared.application.contexto import TenantContext
from app.shared.infrastructure.transacao import abrir_transacao_de_comando

logger = logging.getLogger("nivelo.api.convites")

router = APIRouter(prefix="/api/convites", tags=["convites"])


@router.post(
    "",
    response_model=ConviteOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        402: {"description": "A equipe já está no limite do plano"},
        403: {"description": "Só o dono convida"},
        404: {"description": "Obra não encontrada"},
    },
)
async def convidar(
    payload: ConviteIn,
    request: Request,
    ctx: TenantContext = Depends(requer_papel("dono")),
    db: Session = Depends(sessao_do_tenant),
    equipe: EquipeDaEmpresa = Depends(equipe_da_empresa),
) -> Any:
    """Só o dono. A obra, se informada, precisa ser da empresa ativa (senão 404). Convidar um
    encarregado passa pela política de plano; clientes são ilimitados."""
    if payload.obra_id is not None and not obra_existe(db, payload.obra_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra não encontrada")
    if payload.papel == "encarregado":
        abrir_transacao_de_comando(db)
        efetivos = request.app.state.consulta_direitos(db).travar_e_obter(ctx.empresa_id)
        PoliticaDePlano.exigir_vaga_na_equipe(efetivos, equipe.pessoas_que_contam_no_plano())
    return await forward_request(
        "POST",
        "/convites",
        json_data=payload.model_dump(mode="json"),
        headers={"authorization": request.headers.get("authorization", "")},
    )


@router.post("/aceitar", response_model=AceiteOut, responses={400: {"description": "Convite inválido"}})
async def aceitar(payload: AceiteIn, db: Session = Depends(get_db)) -> Any:
    """Público: o token do e-mail é a credencial. Cria ou reaproveita a conta e entra na obra."""
    resultado = await forward_request("POST", "/convites/aceitar", json_data=payload.model_dump(mode="json"))
    if resultado.get("obra_id"):
        try:
            adicionar_membro(
                db,
                uuid.UUID(resultado["empresa_id"]),
                uuid.UUID(resultado["obra_id"]),
                int(resultado["usuario_id"]),
                resultado["papel"],
            )
        except Exception:
            # O vínculo já existe; o dono pode adicionar o membro à obra depois (Fase 4)
            logger.exception("convite aceito, mas o membro da obra %s não foi gravado", resultado["obra_id"])
    return resultado
