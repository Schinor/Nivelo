#!/usr/bin/env bash
# Regra 8 do projeto: nenhuma referência ao domínio antigo no repositório inteiro.
# Equivale a: git grep -niE com os cinco termos proibidos (ver docs/adr/007).
# As classes de caractere ([a], [i]...) casam as palavras sem que este arquivo contenha nenhuma delas.
set -uo pipefail

padrao='h[a]nks|f[i]lme|t[m]db|m[o]vie|p[o]ster'

if git grep -niE "$padrao"; then
  echo "Encontrei referências ao domínio antigo (acima). Remova-as antes de continuar." >&2
  exit 1
fi
echo "Nenhuma referência ao domínio antigo."
