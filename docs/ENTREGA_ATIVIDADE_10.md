# Entrega da Atividade 10 — Seu negócio no ar

> Situação em 09/11/2026 21:48 (horário de Brasília). Só está marcado o que foi conferido. O prazo era 06/11; a data que vale é a de abertura da issue de entrega.

Sistema: <https://marcio-mazega-isw055.lapps.studio>

## Checklist

| Item | Situação | Evidência ou como fazer |
|---|---|---|
| Landing pública no subdomínio | ✅ | `GET /` responde 200 com o título "Nivelo — Diário de obra"; `/health/ready` responde 200. Falta o print com a barra de endereço |
| Conta dono (empresa A), encarregado convidado na A e dono da empresa B | ☐ | Criar em produção com e-mails seus |
| Dono A: criar, editar e apagar obra; registrar diário com foto | ☐ | `e2e/rodar.sh dono --base <url> ...` (ver `e2e/README.md`) ou pela tela |
| Dono B abre a obra de A e recebe 404 | ☐ | Print do curl e da tela (comando abaixo) |
| Encarregado faz `POST /obras` e recebe 403 | ☐ | Print do curl (comando abaixo) |
| Admin vê no log quem fez e quando | ☐ | Print do Painel (`/admin`, tabela de eventos) |
| Foto no bucket | ☐ | Print do Garage com o `object_key` |
| Stack no Portainer com containers saudáveis | ☐ | Print sem mostrar valores de variáveis |
| Busca pelo domínio antigo vazia (`scripts/checar_dominio_antigo.sh`) | ✅ | Conferido em 09/11. Falta o print |
| README com a URL, diagrama Mermaid e menção a github.com/siriani | ✅ | Seções do topo e 10 do `README.md` |
| `db/001_dominio.sql` versionado | ✅ | [`db/001_dominio.sql`](../db/001_dominio.sql) |

## Comandos dos prints

```bash
URL=https://marcio-mazega-isw055.lapps.studio
TOKEN_ENCARREGADO='<token do login do encarregado>'
TOKEN_DONO_B='<token do login do dono B>'
OBRA_DE_A='<id da obra da empresa A>'

# 403: encarregado tentando criar obra
curl -i -X POST "$URL/api/obras" -H "Authorization: Bearer $TOKEN_ENCARREGADO" \
  -H 'Content-Type: application/json' -d '{}'

# 404: dono da empresa B abrindo a obra da empresa A
curl -i "$URL/api/obras/$OBRA_DE_A" -H "Authorization: Bearer $TOKEN_DONO_B"
```

O token sai da resposta de `POST /api/auth/login`. Não deixe o valor dele aparecer no print.

## Cobertura automática

Os testes rodam no CI a cada push e complementam os prints, sem substituí-los.

| Regra | Onde |
|---|---|
| Tenancy (404 entre empresas) | `tests/test_obras_crud_api.py`, `tests/test_diarios_api.py` |
| Papel (403) | `tests/test_obras_crud_api.py`, `tests/test_diarios_api.py`, `tests/test_admin_api.py` |
| Fotos | `tests/test_fotos_storage.py` |
| Eventos de auditoria | `tests/test_outbox.py`, `tests/test_log_service.py` |

## Issue de entrega

Título: `Entrega — Seu negócio no ar`

Corpo, mencionando `@siriani`: link do commit entregue, URL do sistema e prints acima, cada um com data e hora visíveis.
