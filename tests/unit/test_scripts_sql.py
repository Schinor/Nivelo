"""Divisão dos arquivos .sql de db/ em comandos."""


def test_divide_por_ponto_e_virgula_no_fim_da_linha_e_ignora_comentarios(api):
    scripts_sql = api("app.shared.infrastructure.scripts_sql")
    script = """-- Gerado pelo Alembic
CREATE TABLE a (
    id INT
);

-- Running upgrade x -> y
INSERT INTO a VALUES (1);
INSERT INTO b (texto) VALUES ('chuva; obra parada às 14:00');
UPDATE alembic_version SET version_num='y'"""

    assert scripts_sql.dividir(script) == [
        "CREATE TABLE a (\n    id INT\n)",
        "INSERT INTO a VALUES (1)",
        "INSERT INTO b (texto) VALUES ('chuva; obra parada às 14:00')",
        "UPDATE alembic_version SET version_num='y'",
    ]


def test_script_vazio_ou_so_comentarios_nao_tem_comandos(api):
    scripts_sql = api("app.shared.infrastructure.scripts_sql")
    assert scripts_sql.dividir("") == []
    assert scripts_sql.dividir("-- nada\n  -- mesmo\n") == []
