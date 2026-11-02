"""Perfil de usuário: nome, bio e foto (object storage).

Requisito central: cada um só edita o PRÓPRIO perfil. O `{usuario_id}` da rota
existe só para ser comparado com o id do JWT — nunca é a fonte da identidade.
Admin não é exceção (decisão documentada no README).
"""
import logging
import time
import uuid
from collections import defaultdict, deque
from io import BytesIO
from typing import Optional

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.clients import log_client
from app.clients.auth_client import forward_request
from app.core.api_responses import AUTH_SERVICE_INDISPONIVEL, NOT_FOUND_USER, UNAUTHORIZED
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import current_user, negar_acesso
from app.models.perfil import Perfil
from app.repositories import perfil_repo
from app.schemas.perfil import PerfilBioUpdate, PerfilOut
from app.services import storage

logger = logging.getLogger("nivelo.api.perfis")

router = APIRouter(prefix="/api/perfis", tags=["perfis"])

FORMATOS_ACEITOS = {"JPEG", "PNG", "WEBP"}
LADO_AVATAR = 512
CHUNK_BYTES = 64 * 1024
# Proteção contra decompression bomb (imagem pequena em bytes, gigante em pixels)
Image.MAX_IMAGE_PIXELS = 25_000_000

UPLOADS_POR_MINUTO = 10
_uploads_recentes: dict[int, deque] = defaultdict(deque)

FORBIDDEN_DONO = {
    403: {
        "description": "Perfil de outro usuário — inclusive para admin (evento 'acesso_negado' é registrado)",
        "content": {"application/json": {"example": {"detail": "Você só pode editar o próprio perfil"}}},
    }
}

ERROS_UPLOAD = {
    400: {"description": "Arquivo vazio", "content": {"application/json": {"example": {"detail": "Arquivo vazio"}}}},
    413: {
        "description": "Arquivo maior que PERFIL_FOTO_MAX_BYTES",
        "content": {"application/json": {"example": {"detail": "Imagem maior que o limite de 2 MB"}}},
    },
    415: {
        "description": "Conteúdo não é JPEG/PNG/WEBP (conferido pelos bytes, não pela extensão)",
        "content": {"application/json": {"example": {"detail": "Envie uma imagem JPEG, PNG ou WEBP"}}},
    },
    429: {
        "description": "Muitos uploads em pouco tempo",
        "content": {"application/json": {"example": {"detail": "Muitos envios de foto; aguarde um minuto"}}},
    },
    502: {
        "description": "Object storage indisponível (banco não é alterado)",
        "content": {"application/json": {"example": {"detail": "Storage indisponível"}}},
    },
}


async def _dados_da_conta(usuario_id: int) -> dict:
    """Nome e plano vêm do auth-service (dono da tabela usuarios); 404 se o usuário não existir."""
    return await forward_request("GET", f"/users/{usuario_id}")


async def _montar_perfil(db: Session, usuario_id: int, user: dict, perfil: Optional[Perfil] = None) -> PerfilOut:
    conta = await _dados_da_conta(usuario_id)
    if perfil is None:
        perfil = perfil_repo.get(db, usuario_id)

    foto_url = None
    if perfil and perfil.foto_key:
        foto_url = await run_in_threadpool(storage.url_assinada, perfil.foto_key, perfil.foto_bytes or 0)

    return PerfilOut(
        usuario_id=usuario_id,
        nome=conta.get("nome", ""),
        bio=perfil.bio if perfil else None,
        foto_url=foto_url,
        pode_editar=usuario_id == user["id"],
        premium=bool(conta.get("premium")),
    )


async def garantir_dono(usuario_id_rota: int, user: dict, request: Request) -> None:
    """Compara o id da rota com o id do JWT. Nenhum papel/permissão abre exceção."""
    if usuario_id_rota != user["id"]:
        raise negar_acesso(request, user["id"], f"perfil:{usuario_id_rota}", "Você só pode editar o próprio perfil")


def _checar_limite_upload(usuario_id: int) -> None:
    """Janela deslizante em memória (por processo): no máximo UPLOADS_POR_MINUTO por usuário."""
    agora = time.monotonic()
    janela = _uploads_recentes[usuario_id]
    while janela and agora - janela[0] > 60:
        janela.popleft()
    if len(janela) >= UPLOADS_POR_MINUTO:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Muitos envios de foto; aguarde um minuto")
    janela.append(agora)


async def _ler_com_limite(arquivo: UploadFile, limite: int) -> bytes:
    """Lê em chunks e para assim que passar do limite, sem ler o resto."""
    buffer = bytearray()
    while chunk := await arquivo.read(CHUNK_BYTES):
        buffer.extend(chunk)
        if len(buffer) > limite:
            raise HTTPException(
                status_code=413,
                detail=f"Imagem maior que o limite de {limite // (1024 * 1024)} MB",
            )
    if not buffer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio")
    return bytes(buffer)


def _reencodar_avatar(dados: bytes) -> bytes:
    """Confere o tipo REAL pelos bytes e regrava como WEBP 512x512.

    O re-encode descarta EXIF (GPS, câmera), neutraliza arquivos poliglotas e padroniza o tamanho.
    content_type e extensão enviados pelo cliente são ignorados.
    """
    try:
        with Image.open(BytesIO(dados)) as img:
            formato = img.format
            img.verify()
        if formato not in FORMATOS_ACEITOS:
            raise ValueError(formato)

        # verify() invalida o objeto: reabre para processar
        with Image.open(BytesIO(dados)) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
            img = ImageOps.fit(img, (LADO_AVATAR, LADO_AVATAR))
            saida = BytesIO()
            img.save(saida, format="WEBP", quality=85)
            return saida.getvalue()
    except Exception:  # UnidentifiedImageError, DecompressionBombError, arquivo truncado, formato fora da lista…
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Envie uma imagem JPEG, PNG ou WEBP",
        )


def _apagar_em_best_effort(chave: str) -> None:
    """Síncrono: como BackgroundTask, o Starlette já o executa no threadpool."""
    try:
        storage.apagar_objeto(chave)
    except Exception:
        logger.warning("não foi possível apagar o objeto %s do storage", chave)


@router.get(
    "/me",
    response_model=PerfilOut,
    responses={**UNAUTHORIZED, **AUTH_SERVICE_INDISPONIVEL},
)
async def meu_perfil(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    """Perfil do usuário logado."""
    return await _montar_perfil(db, user["id"], user)


@router.get(
    "/{usuario_id}",
    response_model=PerfilOut,
    responses={**UNAUTHORIZED, **NOT_FOUND_USER, **AUTH_SERVICE_INDISPONIVEL},
)
async def ver_perfil(usuario_id: int, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    """Perfil de qualquer usuário (leitura aberta a quem está logado)."""
    return await _montar_perfil(db, usuario_id, user)


@router.put(
    "/{usuario_id}",
    response_model=PerfilOut,
    responses={**UNAUTHORIZED, **FORBIDDEN_DONO, **AUTH_SERVICE_INDISPONIVEL},
)
async def atualizar_bio(
    usuario_id: int,
    payload: PerfilBioUpdate,
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Atualiza a bio (até 280 caracteres; vazia vira null). Só o dono."""
    await garantir_dono(usuario_id, user, request)
    perfil = perfil_repo.atualizar_bio(db, user["id"], payload.bio)
    background.add_task(
        log_client.registrar, "perfil_atualizado", request, usuario_id=user["id"], recurso=f"perfil:{user['id']}"
    )
    return await _montar_perfil(db, user["id"], user, perfil)


@router.put(
    "/{usuario_id}/foto",
    response_model=PerfilOut,
    responses={**UNAUTHORIZED, **FORBIDDEN_DONO, **ERROS_UPLOAD, **AUTH_SERVICE_INDISPONIVEL},
)
async def enviar_foto(
    usuario_id: int,
    request: Request,
    background: BackgroundTasks,
    foto: UploadFile = File(..., description="JPEG, PNG ou WEBP (máx. PERFIL_FOTO_MAX_BYTES)"),
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Envia/troca a foto. O arquivo vai para o object storage; o banco guarda só a chave."""
    # 1. Dono primeiro — antes de tocar no conteúdo do arquivo
    await garantir_dono(usuario_id, user, request)
    _checar_limite_upload(user["id"])

    # 2-4. Tamanho (streaming), tipo real e re-encode
    dados_originais = await _ler_com_limite(foto, settings.PERFIL_FOTO_MAX_BYTES)
    dados = await run_in_threadpool(_reencodar_avatar, dados_originais)

    # 5. Chave gerada pelo servidor — o nome original do arquivo nunca é usado
    chave = f"avatares/{user['id']}/{uuid.uuid4().hex}.webp"

    # 6. Storage primeiro: se falhar, o banco continua intocado
    try:
        await run_in_threadpool(storage.enviar_objeto, chave, dados, "image/webp")
    except (BotoCoreError, ClientError):
        logger.exception("falha ao enviar %s ao storage", chave)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage indisponível")

    # 7. Banco: se falhar, desfaz o objeto novo
    atual = perfil_repo.get(db, user["id"])
    chave_antiga = atual.foto_key if atual else None
    try:
        perfil = perfil_repo.definir_foto(db, user["id"], chave, len(dados))
    except Exception:
        db.rollback()
        await run_in_threadpool(_apagar_em_best_effort, chave)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao salvar o perfil")

    # 8. Só agora a foto antiga sai do storage
    if chave_antiga and chave_antiga != chave:
        background.add_task(_apagar_em_best_effort, chave_antiga)

    # 9. Auditoria (não bloqueia a resposta)
    background.add_task(
        log_client.registrar,
        "perfil_foto_atualizada",
        request,
        usuario_id=user["id"],
        recurso=f"perfil:{user['id']}",
        detalhes=chave,
    )
    return await _montar_perfil(db, user["id"], user, perfil)


@router.delete(
    "/{usuario_id}/foto",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**UNAUTHORIZED, **FORBIDDEN_DONO},
)
async def remover_foto(
    usuario_id: int,
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Remove a foto (idempotente: sem foto também devolve 204)."""
    await garantir_dono(usuario_id, user, request)
    perfil = perfil_repo.get(db, user["id"])
    if perfil and perfil.foto_key:
        chave = perfil.foto_key
        # Banco primeiro: nunca fica uma chave apontando para objeto inexistente
        perfil_repo.definir_foto(db, user["id"], None, None)
        background.add_task(_apagar_em_best_effort, chave)
        background.add_task(
            log_client.registrar,
            "perfil_foto_removida",
            request,
            usuario_id=user["id"],
            recurso=f"perfil:{user['id']}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
