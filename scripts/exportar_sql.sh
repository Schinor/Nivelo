#!/usr/bin/env bash
# Exporta para db/ o SQL (dialeto MariaDB) de um intervalo de revisões do Alembic, sem banco.
#
# Uso: scripts/exportar_sql.sh <servico> <de>:<ate> <arquivo>
#   servico: api (backend/) ou auth (auth-service/)
#   de:ate:  revisões do Alembic; use "base" para começar do zero
#   arquivo: nome em db/, no formato NNN_descricao.sql
#
# Exemplo: scripts/exportar_sql.sh api api_001_perfis:api_002_remove_catalogo 000_remove_catalogo.sql
#
# O modo offline do Alembic não lê o banco, então a URL abaixo é só para escolher o dialeto.
# Migrações que inspecionam o banco precisam tratar o modo offline (ver api_001_perfis).
set -euo pipefail

if [ "$#" -ne 3 ]; then
  sed -n '2,12p' "$0"
  exit 1
fi

servico="$1"; intervalo="$2"; arquivo="$3"
raiz="$(cd "$(dirname "$0")/.." && pwd)"

case "$servico" in
  api) pasta="$raiz/backend" ;;
  auth) pasta="$raiz/auth-service" ;;
  *) echo "servico deve ser api ou auth" >&2; exit 1 ;;
esac

alembic="${ALEMBIC:-$raiz/.venv/bin/alembic}"
saida="$raiz/db/$arquivo"

{
  echo "-- Gerado por scripts/exportar_sql.sh a partir do Alembic ($servico, $intervalo). Não edite à mão."
  echo "-- Dialeto: MariaDB."
  cd "$pasta"
  DATABASE_URL="mysql+pymysql://exportar@localhost/nivelo" SECRET_KEY="so-para-exportar" \
    "$alembic" upgrade "$intervalo" --sql 2>/dev/null
} > "$saida"

echo "SQL gravado em db/$arquivo"
