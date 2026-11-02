# ADR 008 — Alembic por serviço, com SQL exportado em `db/`

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

O sistema herdado criava as tabelas com `create_all` no boot e corrigia colunas com `ALTER` condicionais no código. O `auth-service` tinha migrações Alembic, mas elas não rodavam no boot. A disciplina pede o esquema versionado em SQL (`db/001_dominio.sql`).

## Decisão

- **Alembic continua sendo a ferramenta**, com uma árvore por serviço dono das tabelas: `auth-service/migrations/` (Identidade) e `backend/migrations/` (Gestão de Obras, Assinaturas e infraestrutura da API).
- Os dois serviços dividem o banco, então cada árvore tem a sua tabela de versão: `alembic_version` (auth) e `alembic_version_api` (API).
- `alembic upgrade head` roda no `CMD` de cada imagem, antes do `uvicorn`. Se a migração falhar, o container não sobe e o deploy quebra na hora.
- `scripts/exportar_sql.sh` gera o SQL das revisões em modo offline, no dialeto do MariaDB, para `db/NNN_descricao.sql`. Migrações que precisam inspecionar o banco tratam o modo offline.
- As migrações são idempotentes para o banco de produção, que já tem as tabelas mas não tem tabela de versão.

## Consequências

- Quem clonar recria o banco pelo Alembic ou aplicando os `.sql` de `db/` em ordem.
- Os `.sql` são gerados, não editados: uma mudança no esquema começa por uma revisão do Alembic.
- A revisão que remove as tabelas do domínio antigo é irreversível de propósito (ADR 007).
