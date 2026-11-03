"""Fixtures compartilhadas entre arquivos de teste."""

import uuid
from datetime import date

import pytest

EMPRESA_A = "0190f3a0-0000-7000-8000-00000000000a"
EMPRESA_B = "0190f3a0-0000-7000-8000-00000000000b"
OBRA_A1 = "0190f3a0-0000-7000-8000-0000000000a1"
OBRA_A2 = "0190f3a0-0000-7000-8000-0000000000a2"
OBRA_B1 = "0190f3a0-0000-7000-8000-0000000000b1"

DONO_A, ENC_A, CLI_A, DONO_B, MULTI = 1, 2, 3, 4, 5


@pytest.fixture
def obras_ctx(monkeypatch):
    """API com obras das empresas A e B e seus membros. MULTI tem vínculo nas duas."""
    from test_backend_proxy import _capturar_eventos, setup_api_app

    app, SessionLocal, _, TestClient = setup_api_app()
    from app.obras.infrastructure.modelos import ObraMembroModel, ObraModel
    from app.shared.infrastructure.tenancy import sem_tenant

    db = SessionLocal()
    with sem_tenant(db, "carga dos dados de teste"):

        def obra(id_, empresa, nome, removida=False):
            from datetime import datetime

            db.add(
                ObraModel(
                    id=uuid.UUID(id_),
                    empresa_id=uuid.UUID(empresa),
                    nome=nome,
                    logradouro="Rua 1",
                    cidade="Marília",
                    uf="SP",
                    cliente_nome="Cliente",
                    data_inicio=date(2026, 10, 1),
                    previsao_termino=date(2026, 12, 1),
                    criado_por=1,
                    removida_em=datetime(2026, 11, 1) if removida else None,
                )
            )

        obra(OBRA_A1, EMPRESA_A, "Casa do Jorge")
        obra(OBRA_A2, EMPRESA_A, "Muro da escola")
        obra(OBRA_B1, EMPRESA_B, "Ampliação Alves")
        obra("0190f3a0-0000-7000-8000-0000000000a9", EMPRESA_A, "Removida", removida=True)
        db.flush()
        db.add_all(
            [
                ObraMembroModel(
                    obra_id=uuid.UUID(OBRA_A1), usuario_id=ENC_A, empresa_id=uuid.UUID(EMPRESA_A), papel="encarregado"
                ),
                ObraMembroModel(
                    obra_id=uuid.UUID(OBRA_A2), usuario_id=CLI_A, empresa_id=uuid.UUID(EMPRESA_A), papel="cliente"
                ),
                ObraMembroModel(
                    obra_id=uuid.UUID(OBRA_A1), usuario_id=MULTI, empresa_id=uuid.UUID(EMPRESA_A), papel="encarregado"
                ),
                ObraMembroModel(
                    obra_id=uuid.UUID(OBRA_B1), usuario_id=MULTI, empresa_id=uuid.UUID(EMPRESA_B), papel="cliente"
                ),
            ]
        )
        db.commit()
    db.close()

    class Ctx:
        pass

    c = Ctx()
    c.client, c.SessionLocal = TestClient(app), SessionLocal
    c.eventos = _capturar_eventos(monkeypatch)
    return c
