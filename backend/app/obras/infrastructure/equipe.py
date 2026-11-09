"""Adaptador da porta `EquipeDaEmpresa`: pergunta ao auth-service quem é da empresa ativa.

Vai com o token de quem chama (o dono): o auth-service confere o vínculo no banco e devolve
só a equipe da empresa do token.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.shared.api.request_id import HEADER as REQUEST_ID_HEADER
from app.shared.api.request_id import obter_request_id
from app.shared.application.erros import DependenciaIndisponivel
from app.shared.domain.ids import UsuarioId

logger = logging.getLogger("nivelo.api.equipe")


class EquipeViaAuthService:
    def __init__(self, authorization: str) -> None:
        self._authorization = authorization
        self._equipe: dict[int, str] | None = None

    def _carregar(self) -> dict[int, str]:
        headers = {"authorization": self._authorization}
        request_id = obter_request_id()
        if request_id:
            headers[REQUEST_ID_HEADER] = request_id
        try:
            resp = httpx.get(f"{settings.AUTH_SERVICE_URL.rstrip('/')}/equipe", headers=headers, timeout=5.0)
            resp.raise_for_status()
            corpo: list[dict[str, Any]] = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("auth-service não respondeu à consulta da equipe", exc_info=True)
            raise DependenciaIndisponivel("Não foi possível conferir a equipe agora. Tente de novo.") from None
        return {int(m["usuario_id"]): str(m["papel"]) for m in corpo}

    def papel_de(self, usuario_id: UsuarioId) -> str | None:
        if self._equipe is None:
            self._equipe = self._carregar()
        return self._equipe.get(usuario_id.valor)

    def pessoas_que_contam_no_plano(self) -> int:
        if self._equipe is None:
            self._equipe = self._carregar()
        return sum(1 for papel in self._equipe.values() if papel in ("dono", "encarregado"))
