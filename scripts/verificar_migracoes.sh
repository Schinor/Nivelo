#!/usr/bin/env bash
# Verifica as migrações num MariaDB de verdade (local ou o service container do CI).
#
# Uso: MARIADB_URL=mysql+pymysql://root:senha@127.0.0.1:3306 scripts/verificar_migracoes.sh
#
# 1. Banco "nivelo_alembic": alembic upgrade head nos dois serviços; a segunda execução não
#    pode aplicar nada; downgrade -1 da revisão de domínio e upgrade de novo.
# 2. Banco "nivelo_sql": aplica só os db/0*.sql, em ordem; depois o alembic não pode ter nada
#    a aplicar (as tabelas de versão batem).
# 3. Os dois bancos precisam ter o mesmo esquema (colunas, tipos, índices e FKs).
# 4. Se existir, aplica o db/900_seed_dev.sql no "nivelo_sql" duas vezes (seed idempotente).
set -euo pipefail

: "${MARIADB_URL:?defina MARIADB_URL, ex.: mysql+pymysql://root:senha@127.0.0.1:3306}"
raiz="$(cd "$(dirname "$0")/.." && pwd)"
py="${PYTHON:-$raiz/.venv/bin/python}"
export SECRET_KEY=verificacao

passo() { printf '\n== %s\n' "$*"; }

recriar() {
  "$py" - "$MARIADB_URL" "$1" <<'PY'
import sys
from sqlalchemy import create_engine
url, banco = sys.argv[1], sys.argv[2]
with create_engine(url).begin() as conn:
    conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {banco}")
    conn.exec_driver_sql(f"CREATE DATABASE {banco} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
PY
}

alembic_em() {  # alembic_em <banco> <servico> <args...>
  local banco="$1" pasta="$2"; shift 2
  (cd "$raiz/$pasta" && DATABASE_URL="$MARIADB_URL/$banco" "$py" -m alembic "$@" 2>&1)
}

sem_mudancas() {  # falha se o alembic aplicou algo
  if grep -q "Running upgrade"; then echo "ERRO: havia revisão pendente" >&2; exit 1; fi
}

passo "1. Alembic do zero (nivelo_alembic)"
recriar nivelo_alembic
for pasta in auth-service backend; do alembic_em nivelo_alembic "$pasta" upgrade head | grep "Running upgrade" | sed 's/.*Running/  Running/'; done
for pasta in auth-service backend; do alembic_em nivelo_alembic "$pasta" upgrade head | sem_mudancas; done
echo "  segunda execução: nada a aplicar"
for pasta in backend auth-service; do alembic_em nivelo_alembic "$pasta" downgrade -1 | grep "Running downgrade" | sed 's/.*Running/  Running/'; done
for pasta in auth-service backend; do alembic_em nivelo_alembic "$pasta" upgrade head | grep "Running upgrade" | sed 's/.*Running/  Running/'; done

passo "2. Só os db/0*.sql (nivelo_sql)"
recriar nivelo_sql
(cd "$raiz/backend" && "$py" -m app.shared.infrastructure.scripts_sql "$MARIADB_URL/nivelo_sql" "$raiz"/db/0*.sql)
for pasta in auth-service backend; do alembic_em nivelo_sql "$pasta" upgrade head | sem_mudancas; done
echo "  alembic depois dos .sql: nada a aplicar"

passo "3. Mesmo esquema nos dois bancos"
"$py" - "$MARIADB_URL" <<'PY'
import sys
from sqlalchemy import create_engine
url = sys.argv[1]
consultas = {
    "colunas": "SELECT table_name, column_name, column_type, is_nullable, column_default"
               " FROM information_schema.columns WHERE table_schema = %s",
    "indices": "SELECT table_name, index_name, non_unique, seq_in_index, column_name"
               " FROM information_schema.statistics WHERE table_schema = %s",
    "fks": "SELECT r.table_name, r.constraint_name, r.referenced_table_name, r.delete_rule"
           " FROM information_schema.referential_constraints r WHERE r.constraint_schema = %s",
}
with create_engine(url).connect() as conn:
    for nome, sql in consultas.items():
        a = set(conn.exec_driver_sql(sql, ("nivelo_alembic",)).fetchall())
        b = set(conn.exec_driver_sql(sql, ("nivelo_sql",)).fetchall())
        if a != b:
            print(f"ERRO: {nome} diferentes\n  só no alembic: {sorted(a - b)[:5]}\n  só no sql: {sorted(b - a)[:5]}")
            sys.exit(1)
        print(f"  {nome}: {len(a)} iguais")
PY

if [ -f "$raiz/db/900_seed_dev.sql" ]; then
  passo "4. Seed de desenvolvimento, duas vezes (nivelo_sql)"
  for _ in 1 2; do
    (cd "$raiz/backend" && "$py" -m app.shared.infrastructure.scripts_sql "$MARIADB_URL/nivelo_sql" "$raiz/db/900_seed_dev.sql")
  done
  "$py" - "$MARIADB_URL/nivelo_sql" <<'PY'
import sys
from sqlalchemy import create_engine
esperado = {"empresas": 2, "usuarios": 6, "vinculos": 6, "assinaturas": 2, "obras": 2,
            "obra_membros": 4, "diarios": 3, "ocorrencias": 1, "comentarios": 1}
with create_engine(sys.argv[1]).connect() as conn:
    contagem = {t: conn.exec_driver_sql(f"SELECT COUNT(*) FROM {t}").scalar() for t in esperado}
print("  linhas:", contagem)
if contagem != esperado:
    print(f"ERRO: esperado {esperado}")
    sys.exit(1)
PY
fi

passo "OK: migrações verificadas"
