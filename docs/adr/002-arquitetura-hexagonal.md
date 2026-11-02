# ADR 002 — Arquitetura hexagonal em cada contexto da API

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

As regras do diário de obra (um diário por dia, diário publicado não se sobrescreve, limites do plano) são o valor do produto. No código herdado, a regra fica espalhada entre rota, repositório e modelo ORM, e não há como testá-la sem banco.

## Decisão

Cada contexto da API (`shared`, `obras`, `assinaturas`) se divide em quatro camadas, dentro de `backend/app/`:

```
domain/          agregados, value objects, eventos, portas — Python puro
application/     comandos, handlers, queries e DTOs
infrastructure/  repositórios SQLAlchemy, gateways (S3, Stripe), outbox
api/             routers FastAPI e schemas Pydantic
```

- Dependências: `api → infrastructure → application → domain`. O domínio não importa nada de fora.
- O `import-linter` no CI quebra o build se o domínio importar FastAPI, Starlette, SQLAlchemy, Redis, boto3, Stripe, httpx, Pydantic ou o código herdado, ou se uma camada importar uma camada de cima.
- O mypy roda em modo `strict` no `domain/`.
- O `admin/` só tem consultas (read model) e nenhum contexto depende dele.
- **Layout real:** o roteiro desenhava `services/api/app/`; mantivemos `backend/app/` para não mexer no `Dockerfile`, no workflow e no build do front agora. Os módulos herdados (`core`, `routes`, `clients`, `models`, `repositories`, `schemas`, `services`) convivem com o esqueleto e migram para os contextos conforme cada fase os tocar.

## Consequências

- O domínio é testado sem banco e sem HTTP (`tests/unit/`).
- Há mais arquivos e um mapeamento ORM ↔ domínio a manter.
- Enquanto o código herdado existir, o lint tem exceções documentadas para ele no `pyproject.toml`. Código novo não tem exceção.
