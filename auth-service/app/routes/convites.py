"""Convites: o dono convida por e-mail para um papel (e uma obra); o aceite cria ou reaproveita a
conta e cria o vínculo. Token guardado só como hash SHA-256, validade de 72 h, uso único."""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.api_responses import UNAUTHORIZED
from app.core.config import settings
from app.core.database import get_db
from app.core.email import send_convite_email
from app.core.security import SessaoAtual, hash_password, sessao_atual
from app.models.convite import Convite
from app.models.empresa import Vinculo
from app.models.usuario import Usuario
from app.repositories import identidade_repo, usuario_repo
from app.schemas.convite import AceiteIn, AceiteOut, ConviteIn, ConviteOut

logger = logging.getLogger("auth-service.convites")

router = APIRouter(tags=["convites"])

CONVITE_INVALIDO = "Convite inválido, já usado ou expirado. Peça um novo convite a quem convidou você."


def hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _agora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@router.post(
    "/convites",
    response_model=ConviteOut,
    status_code=status.HTTP_201_CREATED,
    responses={**UNAUTHORIZED, 403: {"description": "Só o dono convida"}, 409: {"description": "Já faz parte"}},
)
def convidar(payload: ConviteIn, sessao: SessaoAtual = Depends(sessao_atual), db: Session = Depends(get_db)):
    """O dono da empresa ativa convida por e-mail. O vínculo é conferido no banco, não só no token."""
    if not sessao.empresa_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Escolha ou crie uma empresa para convidar pessoas")
    empresa_id = uuid.UUID(sessao.empresa_id)
    meu = identidade_repo.vinculo(db, sessao.usuario.id, empresa_id)
    if meu is None or not meu.ativo or meu.papel != "dono":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o dono da empresa convida pessoas")

    email = payload.email.strip().lower()
    convidado = usuario_repo.get_by_email(db, email)
    if convidado is not None:
        existente = identidade_repo.vinculo(db, convidado.id, empresa_id)
        if existente is not None and existente.ativo:
            raise HTTPException(status.HTTP_409_CONFLICT, "Essa pessoa já faz parte da empresa")

    token = secrets.token_urlsafe(32)
    convite = Convite(
        empresa_id=empresa_id,
        email=email,
        papel=payload.papel,
        obra_id=payload.obra_id,
        token_hash=hash_do_token(token),
        expira_em=_agora() + timedelta(hours=settings.CONVITE_VALIDADE_HORAS),
        criado_por=sessao.usuario.id,
    )
    db.add(convite)
    db.commit()
    db.refresh(convite)

    try:
        send_convite_email(email, token, meu.empresa.nome, payload.papel, sessao.usuario.nome)
    except Exception:
        # O convite fica registrado; o dono pode convidar de novo (um convite novo invalida nada)
        logger.warning("convite %s criado, mas o e-mail não foi enviado", convite.id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Convite criado, mas o e-mail não pôde ser enviado")
    return convite


@router.post("/convites/aceitar", response_model=AceiteOut, responses={400: {"description": CONVITE_INVALIDO}})
def aceitar(payload: AceiteIn, db: Session = Depends(get_db)):
    """Aceita o convite: reaproveita a conta do e-mail ou cria uma nova, e cria o vínculo."""
    convite = db.query(Convite).filter(Convite.token_hash == hash_do_token(payload.token)).first()
    if convite is None or convite.usado_em is not None or convite.expira_em <= _agora():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CONVITE_INVALIDO)

    # Uso único mesmo com dois aceites ao mesmo tempo: só um UPDATE pega o convite livre
    marcado = db.execute(
        update(Convite)
        .where(Convite.id == convite.id, Convite.usado_em.is_(None))
        .values(usado_em=_agora())
        .execution_options(synchronize_session=False)
    )
    if marcado.rowcount != 1:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CONVITE_INVALIDO)

    usuario = usuario_repo.get_by_email(db, convite.email)
    novo_usuario = usuario is None
    if novo_usuario:
        if not payload.nome or not payload.senha:
            db.rollback()
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Informe nome e senha para criar sua conta")
        usuario = Usuario(nome=payload.nome.strip(), email=convite.email, senha_hash=hash_password(payload.senha))
        db.add(usuario)
        db.flush()

    vinculo = identidade_repo.vinculo(db, usuario.id, convite.empresa_id)
    if vinculo is None:
        vinculo = Vinculo(usuario_id=usuario.id, empresa_id=convite.empresa_id, papel=convite.papel)
        db.add(vinculo)
    elif not vinculo.ativo:
        vinculo.ativo = True
        vinculo.papel = convite.papel
    # Vínculo ativo já existente mantém o papel: um convite nunca rebaixa ninguém
    db.commit()

    return AceiteOut(
        usuario_id=usuario.id,
        empresa_id=convite.empresa_id,
        papel=vinculo.papel,
        obra_id=convite.obra_id,
        novo_usuario=novo_usuario,
    )
