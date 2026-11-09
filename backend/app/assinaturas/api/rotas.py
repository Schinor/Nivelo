"""Rotas de Assinaturas. O plano vem sempre do banco, e a empresa, só do token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.assinaturas.api.schemas import AssinaturaOut, DireitosOut, UsoOut
from app.assinaturas.infrastructure.repositorio import RepositorioDeAssinaturasSQL
from app.obras.api.dependencias import equipe_da_empresa
from app.obras.application.portas import EquipeDaEmpresa
from app.shared.api.autenticacao import requer_papel
from app.shared.api.sessao import sessao_do_tenant
from app.shared.application.contexto import TenantContext

router = APIRouter(prefix="/api", tags=["assinaturas"])


@router.get("/assinatura", response_model=AssinaturaOut, responses={403: {"description": "Só o dono"}})
def consultar_assinatura(
    request: Request,
    ctx: TenantContext = Depends(requer_papel("dono")),
    db: Session = Depends(sessao_do_tenant),
    equipe: EquipeDaEmpresa = Depends(equipe_da_empresa),
) -> AssinaturaOut:
    """Plano, status, direitos e uso atual da empresa ativa."""
    assinatura = RepositorioDeAssinaturasSQL(db).obter(ctx.empresa_id)
    uso = request.app.state.uso_do_plano(db, ctx.empresa_id, equipe).uso_atual()
    d = assinatura.efetivos.direitos
    return AssinaturaOut(
        plano=assinatura.plano.value,
        plano_efetivo=assinatura.efetivos.plano.value,
        status=assinatura.status.value,
        tem_assinatura_vigente=assinatura.tem_assinatura_vigente,
        periodo_fim=assinatura.periodo_fim,
        cancelar_no_fim=assinatura.cancelar_no_fim,
        direitos=DireitosOut(
            max_obras_ativas=d.max_obras_ativas,
            max_fotos_por_obra=d.max_fotos_por_obra,
            max_membros_equipe=d.max_membros_equipe,
            logo_no_relatorio=d.logo_no_relatorio,
        ),
        uso=UsoOut(
            obras_ativas=uso.obras_ativas,
            fotos_na_obra_mais_cheia=uso.fotos_na_obra_mais_cheia,
            membros_equipe=uso.membros_equipe,
        ),
    )
