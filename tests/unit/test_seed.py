"""Seed de desenvolvimento: só age com SEED ligado e encontra o arquivo no repositório."""

import pytest


@pytest.mark.parametrize("valor", ["true", "TRUE", " 1 ", "sim", "on"])
def test_seed_ligado(api, valor):
    assert api("app.shared.infrastructure.seed").seed_ligado(valor) is True


@pytest.mark.parametrize("valor", [None, "", "false", "0", "nao", "talvez"])
def test_seed_desligado(api, valor):
    assert api("app.shared.infrastructure.seed").seed_ligado(valor) is False


def test_sem_seed_nao_toca_no_banco(api):
    seed = api("app.shared.infrastructure.seed")
    # URL inválida de propósito: se tentasse conectar, falharia
    assert seed.executar("mysql+pymysql://ninguem@host-que-nao-existe/x", "false") == 0


def test_encontra_o_arquivo_de_seed_no_repositorio(api):
    seed = api("app.shared.infrastructure.seed")
    arquivo = seed.localizar_seed()
    assert arquivo.name == "900_seed_dev.sql" and arquivo.parent.name == "db"


def test_seed_e_idempotente_por_construcao(api):
    """Todo comando do seed é INSERT IGNORE: rodar duas vezes não duplica nada."""
    seed = api("app.shared.infrastructure.seed")
    scripts_sql = api("app.shared.infrastructure.scripts_sql")
    comandos = scripts_sql.dividir(seed.localizar_seed().read_text(encoding="utf-8"))
    assert comandos and all(c.startswith("INSERT IGNORE INTO") for c in comandos)


@pytest.mark.parametrize("app_env", ["production", "PRODUCTION", " producao ", "prod"])
def test_seed_ligado_em_producao_e_recusado(api, app_env):
    seed = api("app.shared.infrastructure.seed")
    with pytest.raises(seed.SeedEmProducaoError):
        seed.executar("mysql+pymysql://ninguem@host-que-nao-existe/x", "true", app_env)


def test_seed_desligado_em_producao_e_permitido(api):
    seed = api("app.shared.infrastructure.seed")
    assert seed.executar("mysql+pymysql://ninguem@host-que-nao-existe/x", "false", "production") == 0


def test_boot_falha_com_seed_em_producao():
    """O módulo roda no CMD da imagem antes do uvicorn: sair com código 1 derruba o boot."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    raiz_api = Path(__file__).resolve().parents[2] / "backend"
    env = {**os.environ, "DATABASE_URL": "sqlite://", "SEED": "true", "APP_ENV": "production"}
    resultado = subprocess.run(
        [sys.executable, "-m", "app.shared.infrastructure.seed"], cwd=raiz_api, env=env, capture_output=True, text=True
    )
    assert resultado.returncode == 1
    assert "APP_ENV=production" in resultado.stderr
