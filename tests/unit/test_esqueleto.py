"""Esqueleto hexagonal (Fase 1): os pacotes existem e o kernel compartilhado se comporta."""
import uuid
from datetime import UTC, datetime

import pytest

PACOTES = [
    "app.shared.domain",
    "app.shared.application",
    "app.shared.infrastructure",
    "app.shared.api",
    "app.obras.domain",
    "app.obras.application",
    "app.obras.infrastructure",
    "app.obras.api",
    "app.assinaturas.domain",
    "app.assinaturas.application",
    "app.assinaturas.infrastructure",
    "app.assinaturas.api",
    "app.admin",
]


@pytest.mark.parametrize("pacote", PACOTES)
def test_pacote_do_esqueleto_existe_e_esta_documentado(api, pacote):
    modulo = api(pacote)
    assert modulo.__doc__ and modulo.__doc__.strip()


def test_uuid7_tem_versao_variante_e_timestamp(api):
    ids = api("app.shared.domain.ids")
    agora_ms = 1_762_131_600_000  # 2025-11-03T00:00:00Z
    gerado = ids.uuid7(agora_ms)

    assert gerado.version == 7
    assert gerado.variant == uuid.RFC_4122
    assert gerado.int >> 80 == agora_ms


def test_uuid7_ordena_pelo_instante_de_criacao(api):
    ids = api("app.shared.domain.ids")
    antes, depois = ids.uuid7(1_000), ids.uuid7(2_000)
    assert antes < depois
    assert ids.uuid7(1_000) != ids.uuid7(1_000)  # parte aleatória


def test_uuid7_recusa_timestamp_fora_de_48_bits(api):
    ids = api("app.shared.domain.ids")
    with pytest.raises(ValueError):
        ids.uuid7(1 << 48)


def test_empresa_id_compara_por_valor_e_valida_texto(api):
    ids = api("app.shared.domain.ids")
    texto = "0190f3a0-0000-7000-8000-000000000001"

    assert ids.EmpresaId.de_texto(texto) == ids.EmpresaId(uuid.UUID(texto))
    assert str(ids.EmpresaId.de_texto(texto)) == texto
    assert ids.EmpresaId.novo().valor.version == 7
    with pytest.raises(ValueError):
        ids.EmpresaId.de_texto("1")  # autoincremento não é identificador público
    with pytest.raises(TypeError):
        ids.EmpresaId("0190f3a0-0000-7000-8000-000000000001")


def test_evento_de_dominio_exige_tipo_recurso_ponto_acao(api):
    eventos = api("app.shared.domain.eventos")
    evento = eventos.EventoDeDominio(tipo="obra.criada")

    assert evento.event_id.version == 7
    assert evento.ocorrido_em.tzinfo is not None and evento.ocorrido_em <= datetime.now(UTC)
    with pytest.raises(ValueError):
        eventos.EventoDeDominio(tipo="obra_criada")


def test_tenant_context_so_aceita_papel_de_negocio(api):
    contexto = api("app.shared.application.contexto")
    ids = api("app.shared.domain.ids")
    empresa = ids.EmpresaId.novo()

    assert contexto.TenantContext(empresa, 1, "encarregado").papel == "encarregado"
    with pytest.raises(ValueError):
        contexto.TenantContext(empresa, 1, "admin")  # o admin é da plataforma, não de uma empresa
