#!/usr/bin/env bash
# Exporta para db/ o SQL (dialeto MariaDB) de intervalos de revisões do Alembic, sem banco.
#
# Uso: scripts/exportar_sql.sh <arquivo> <servico> <de:ate> [<servico> <de:ate> ...]
#   arquivo: nome em db/, no formato NNN_descricao.sql
#   servico: auth (auth-service/) ou api (backend/); a ordem dos pares é a ordem no arquivo
#   de:ate:  revisões do Alembic; "base" começa do zero
#
# Exemplo:
#   scripts/exportar_sql.sh 001_dominio.sql auth 004_premium_stripe:005_identidade \
#     api api_002_remove_catalogo:api_003_dominio
#
# O modo offline não lê o banco: a URL abaixo só escolhe o dialeto (mariadb, para o tipo
# UUID nativo). Migrações que inspecionam o banco tratam o modo offline (ver 001 a 004 do
# auth-service e api_001_perfis). Os arquivos em db/ são gerados: não edite à mão.
set -euo pipefail

if [ "$#" -lt 3 ] || [ $(( ($# - 1) % 2 )) -ne 0 ]; then
  sed -n '2,15p' "$0"
  exit 1
fi

raiz="$(cd "$(dirname "$0")/.." && pwd)"
alembic="${ALEMBIC:-$raiz/.venv/bin/alembic}"
arquivo="$1"; shift
saida="$raiz/db/$arquivo"
temp="$(mktemp)"
trap 'rm -f "$temp"' EXIT

{
  echo "-- Gerado por scripts/exportar_sql.sh a partir do Alembic. Não edite à mão."
  echo "-- Dialeto: MariaDB 10.7+ (tipo UUID nativo). Ordem de aplicação: db/README.md."
  while [ "$#" -gt 0 ]; do
    servico="$1"; intervalo="$2"; shift 2
    case "$servico" in
      api) pasta="$raiz/backend" ;;
      auth) pasta="$raiz/auth-service" ;;
      *) echo "servico deve ser api ou auth: $servico" >&2; exit 1 ;;
    esac
    echo
    echo "-- ===== $servico: $intervalo ====="
    (cd "$pasta" && DATABASE_URL="mariadb+pymysql://exportar@localhost/nivelo" SECRET_KEY="so-para-exportar" \
      "$alembic" upgrade "$intervalo" --sql 2>/dev/null)
  done
} > "$temp"

mv "$temp" "$saida"
trap - EXIT
echo "SQL gravado em db/$arquivo"
