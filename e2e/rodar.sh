#!/usr/bin/env bash
# Roda o e2e/navegar.py dentro da imagem oficial do Playwright (Chromium já instalado),
# com o seu usuário, para os prints não saírem como root.
#
# Uso: e2e/rodar.sh dono --base <url> [opções]   |   e2e/rodar.sh cliente --base <url> --token <t>
# --network host deixa a imagem enxergar o http://localhost:8000 da stack local.
set -euo pipefail
pasta="$(cd "$(dirname "$0")" && pwd)"
imagem="mcr.microsoft.com/playwright/python:v1.58.0-noble"
exec docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$pasta:/e2e" -w /e2e "$imagem" \
  sh -c 'pip install -q --user --disable-pip-version-check -r requirements.txt 2>&1 | grep -v "WARNING" || true; python navegar.py "$@"' \
  navegar "$@"
