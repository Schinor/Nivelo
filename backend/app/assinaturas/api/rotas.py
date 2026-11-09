"""Rotas de Assinaturas. O plano vem sempre do banco, e a empresa, só do token."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.assinaturas.api.dependencias import gateway_de_pagamentos, precos_dos_planos
from app.assinaturas.api.schemas import AssinaturaOut, CheckoutIn, DireitosOut, UrlOut, UsoOut
from app.assinaturas.application.casos_de_uso import abrir_portal, iniciar_checkout
from app.assinaturas.application.portas import GatewayDePagamentos
from app.assinaturas.application.webhook import ResultadoDoAviso, processar_aviso
from app.assinaturas.domain.assinatura import AssinaturaDoWebhookInvalida, EventoDePagamento, PrecosDosPlanos
from app.assinaturas.domain.planos import Plano
from app.assinaturas.infrastructure.livro import LivroDoWebhookSQL
from app.assinaturas.infrastructure.repositorio import RepositorioDeAssinaturasSQL
from app.clients import log_client
from app.clients.auth_client import forward_request
from app.core.database import get_db
from app.obras.api.dependencias import equipe_da_empresa
from app.obras.application.portas import EquipeDaEmpresa
from app.shared.api.autenticacao import Identidade, identidade, requer_papel
from app.shared.api.request_id import obter_request_id
from app.shared.api.sessao import sessao_do_tenant
from app.shared.application.contexto import TenantContext
from app.shared.domain.ids import EmpresaId
from app.shared.infrastructure.outbox import MetadadosDaRequisicao
from app.shared.infrastructure.tenancy import sem_tenant

logger = logging.getLogger("nivelo.api.assinaturas")

router = APIRouter(prefix="/api", tags=["assinaturas"])
webhook_router = APIRouter(tags=["assinaturas"])

AVISOS_POR_MINUTO = 120
_avisos_recentes: dict[str, deque[float]] = defaultdict(deque)


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


@router.post(
    "/assinaturas/checkout",
    response_model=UrlOut,
    responses={403: {"description": "Só o dono"}, 409: {"description": "A empresa já tem assinatura"}},
)
def criar_checkout(
    payload: CheckoutIn,
    ctx: TenantContext = Depends(requer_papel("dono")),
    ident: Identidade = Depends(identidade),
    db: Session = Depends(sessao_do_tenant),
    gateway: GatewayDePagamentos = Depends(gateway_de_pagamentos),
    precos: PrecosDosPlanos = Depends(precos_dos_planos),
) -> UrlOut:
    """Devolve a URL do checkout. O plano só muda quando o webhook confirmar o pagamento."""
    registro = RepositorioDeAssinaturasSQL(db)
    url = iniciar_checkout(
        Plano(payload.plano), ctx, ident.email or None, ident.nome or None, registro, gateway, precos
    )
    return UrlOut(url=url)


@router.post(
    "/assinaturas/portal",
    response_model=UrlOut,
    responses={403: {"description": "Só o dono"}, 409: {"description": "A empresa ainda não assinou"}},
)
def criar_portal(
    ctx: TenantContext = Depends(requer_papel("dono")),
    db: Session = Depends(sessao_do_tenant),
    gateway: GatewayDePagamentos = Depends(gateway_de_pagamentos),
) -> UrlOut:
    """Devolve a URL do portal, onde o dono troca de plano, atualiza o cartão ou cancela."""
    return UrlOut(url=abrir_portal(ctx, RepositorioDeAssinaturasSQL(db), gateway))


def _exigir_folga_no_limite(request: Request) -> None:
    """Janela deslizante em memória, por origem. Acima dela, 429: o Stripe reenvia depois."""
    origem = request.client.host if request.client else "desconhecida"
    agora = time.monotonic()
    janela = _avisos_recentes[origem]
    while janela and agora - janela[0] > 60:
        janela.popleft()
    if len(janela) >= AVISOS_POR_MINUTO:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitos avisos em pouco tempo")
    janela.append(agora)


async def _avisar_inadimplencia(empresa_id: EmpresaId) -> None:
    try:
        await forward_request(
            "POST", "/internal/avisos/inadimplencia", json_data={"empresa_id": str(empresa_id)}, interno=True
        )
    except HTTPException as erro:
        logger.error("e-mail de inadimplência da empresa %s não saiu (%s)", empresa_id, erro.status_code)


def _processar_sem_tenant(
    aviso: EventoDePagamento, gateway: GatewayDePagamentos, db: Session, precos: PrecosDosPlanos, request_id: str | None
) -> ResultadoDoAviso:
    # Exceção de tenancy revisada: não há token, e a empresa vem do evento com assinatura validada
    with sem_tenant(db, "webhook do Stripe"):
        livro = LivroDoWebhookSQL(db, MetadadosDaRequisicao(ator_papel="dono", request_id=request_id))
        return processar_aviso(aviso, gateway, livro, precos)


@webhook_router.post(
    "/webhooks/stripe",
    responses={
        400: {"description": "Assinatura ausente ou inválida"},
        429: {"description": "Muitos avisos em pouco tempo"},
        500: {"description": "Falha ao processar (o Stripe reenvia)"},
        503: {"description": "Stripe não configurado"},
    },
)
async def receber_webhook(
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    gateway: GatewayDePagamentos = Depends(gateway_de_pagamentos),
    precos: PrecosDosPlanos = Depends(precos_dos_planos),
) -> dict[str, bool]:
    """Público, sem JWT: só aceita corpo assinado com o segredo do webhook."""
    _exigir_folga_no_limite(request)
    payload = await request.body()
    try:
        aviso = gateway.validar_evento(payload, request.headers.get("stripe-signature", ""))
    except AssinaturaDoWebhookInvalida:
        logger.warning("webhook do Stripe recusado: assinatura inválida")
        # Direto: tarefa em segundo plano não roda quando a rota responde com erro
        await log_client.registrar("webhook.assinatura_invalida", request, recurso="stripe")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Assinatura inválida") from None

    try:
        resultado = await run_in_threadpool(_processar_sem_tenant, aviso, gateway, db, precos, obter_request_id())
    except Exception:
        # Qualquer falha vira 500: o Stripe reenvia, e a idempotência evita aplicar duas vezes
        logger.exception("webhook do Stripe %s (%s) falhou", aviso.id, aviso.tipo)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Falha ao processar o evento") from None

    logger.info("webhook do Stripe %s (%s): %s", aviso.id, aviso.tipo, resultado.situacao)
    if resultado.avisar_inadimplencia is not None:
        background.add_task(_avisar_inadimplencia, resultado.avisar_inadimplencia)
    return {"ok": True}
