"""Implementação SQLAlchemy da `ConsultaDireitos`: lê a assinatura com `FOR UPDATE`."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assinaturas.domain.planos import DireitosEfetivos, Plano, StatusAssinatura, direitos_efetivos
from app.assinaturas.infrastructure.modelos import AssinaturaModel
from app.assinaturas.infrastructure.repositorio import RepositorioDeAssinaturasSQL
from app.shared.domain.ids import EmpresaId


class ConsultaDireitosSQL:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _travar(self, empresa_id: EmpresaId) -> AssinaturaModel | None:
        consulta = (
            select(AssinaturaModel)
            .where(AssinaturaModel.empresa_id == empresa_id.valor)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._session.scalars(consulta).one_or_none()

    def travar_e_obter(self, empresa_id: EmpresaId) -> DireitosEfetivos:
        existe = self._session.scalar(
            select(AssinaturaModel.empresa_id).where(AssinaturaModel.empresa_id == empresa_id.valor)
        )
        if existe is None:
            # Empresa sem linha de assinatura (anterior à Fase 3, ou a criação no cadastro
            # falhou). A linha Free nasce numa transação própria, já gravada, antes de travar.
            # A leitura acima é sem trava de propósito: um FOR UPDATE numa linha que não existe
            # trava o vão do índice, e aí a inserção da outra transação fica esperando (e duas
            # requisições criando a linha ao mesmo tempo caem em deadlock no InnoDB).
            motor = self._session.get_bind()
            if motor.dialect.name in ("mysql", "mariadb"):
                # Em READ COMMITTED a inserção concorrente vira chave duplicada (tratada no
                # repositório), e não o erro de retrato do REPEATABLE READ (ADR 011)
                motor = motor.execution_options(isolation_level="READ COMMITTED")
            with Session(bind=motor) as separada:
                RepositorioDeAssinaturasSQL(separada).garantir_free(empresa_id)
        assinatura = self._travar(empresa_id)
        if assinatura is None:  # pragma: no cover - a linha acabou de ser gravada
            return direitos_efetivos(Plano.FREE, StatusAssinatura.ACTIVE)
        return direitos_efetivos(Plano(assinatura.plano), StatusAssinatura.de_texto(assinatura.status))
