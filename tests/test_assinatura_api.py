"""GET /api/assinatura: plano e uso da empresa ativa, só para o dono."""

import uuid
from datetime import date

import pytest
from conftest import CLI_A, DONO_A, DONO_B, EMPRESA_A, EMPRESA_B, ENC_A, OBRA_A1
from test_obras_api import tk

pytestmark = pytest.mark.mariadb

DONO = tk(DONO_A, EMPRESA_A, "dono")


class EquipeFalsa:
    def pessoas_que_contam_no_plano(self):
        return 2


@pytest.fixture
def ctx(obras_ctx):
    from app.main import app
    from app.obras.api.dependencias import equipe_da_empresa

    app.dependency_overrides[equipe_da_empresa] = EquipeFalsa
    yield obras_ctx
    app.dependency_overrides.pop(equipe_da_empresa, None)


def _assinatura(ctx, empresa, **campos):
    from app.assinaturas.infrastructure.modelos import AssinaturaModel
    from app.shared.infrastructure.tenancy import sem_tenant

    db = ctx.SessionLocal()
    with sem_tenant(db, "carga dos dados de teste"):
        db.merge(AssinaturaModel(empresa_id=uuid.UUID(empresa), **campos))
        db.commit()
    db.close()


def test_empresa_sem_linha_nasce_no_free_com_o_uso_atual(ctx):
    corpo = ctx.client.get("/api/assinatura", headers=DONO).json()

    assert corpo["plano"] == "free" and corpo["plano_efetivo"] == "free" and corpo["status"] == "active"
    assert corpo["tem_assinatura_vigente"] is False
    assert corpo["direitos"]["max_obras_ativas"] == 1
    assert corpo["uso"] == {"obras_ativas": 2, "fotos_na_obra_mais_cheia": 0, "membros_equipe": 2}


def test_uso_conta_as_fotos_da_obra_mais_cheia(ctx):
    from app.obras.infrastructure.modelos import DiarioFotoModel, DiarioModel
    from app.shared.infrastructure.tenancy import sem_tenant

    db = ctx.SessionLocal()
    with sem_tenant(db, "carga dos dados de teste"):
        diario = uuid.uuid4()
        db.add(
            DiarioModel(
                id=diario,
                obra_id=uuid.UUID(OBRA_A1),
                empresa_id=uuid.UUID(EMPRESA_A),
                data=date(2026, 11, 2),
                clima_manha="sol",
                clima_tarde="sol",
                condicao="praticavel",
                atividades="Alvenaria",
                efetivo=3,
                status="rascunho",
                autor_id=DONO_A,
            )
        )
        db.flush()
        for _ in range(3):
            db.add(
                DiarioFotoModel(
                    id=uuid.uuid4(),
                    diario_id=diario,
                    empresa_id=uuid.UUID(EMPRESA_A),
                    object_key=f"k/{uuid.uuid4()}.jpg",
                    content_type="image/jpeg",
                    tamanho_bytes=10,
                    enviado_por=DONO_A,
                )
            )
        db.commit()
    db.close()

    assert ctx.client.get("/api/assinatura", headers=DONO).json()["uso"]["fotos_na_obra_mais_cheia"] == 3


def test_pro_inadimplente_mostra_o_plano_contratado_com_direitos_do_free(ctx):
    _assinatura(ctx, EMPRESA_A, plano="pro", status="past_due", stripe_subscription_id="sub_1")

    corpo = ctx.client.get("/api/assinatura", headers=DONO).json()

    assert corpo["plano"] == "pro" and corpo["plano_efetivo"] == "free"
    assert corpo["direitos"]["max_obras_ativas"] == 1 and corpo["tem_assinatura_vigente"] is True


def test_cada_empresa_ve_so_a_propria_assinatura(ctx):
    _assinatura(ctx, EMPRESA_A, plano="construtora", status="active")

    assert ctx.client.get("/api/assinatura", headers=tk(DONO_B, EMPRESA_B, "dono")).json()["plano"] == "free"


@pytest.mark.parametrize("uid,papel", [(ENC_A, "encarregado"), (CLI_A, "cliente")])
def test_so_o_dono_consulta_a_assinatura(ctx, uid, papel):
    assert ctx.client.get("/api/assinatura", headers=tk(uid, EMPRESA_A, papel)).status_code == 403
