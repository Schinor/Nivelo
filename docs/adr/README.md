# Registros de decisão de arquitetura (ADRs)

Uma página por decisão: contexto, decisão e consequências. Uma decisão nova que muda uma anterior ganha um ADR novo, e o antigo passa a "Substituído por".

| # | Decisão | Status |
|---|---|---|
| [001](001-contextos-delimitados.md) | Contextos delimitados e onde cada um roda | Aceito |
| [002](002-arquitetura-hexagonal.md) | Arquitetura hexagonal em cada contexto da API | Aceito |
| [003](003-outbox-para-eventos.md) | Outbox transacional para os eventos de auditoria | Aceito |
| [004](004-tenancy-por-coluna-e-vinculos.md) | Tenancy por coluna, com usuário global e vínculos | Aceito |
| [005](005-jwt-padrao-b-validade-2h.md) | JWT validado localmente (Padrão B), validade de 2 h | Aceito |
| [006](006-402-para-limite-de-plano.md) | 402 Payment Required para limite de plano | Aceito |
| [007](007-remocao-do-material-da-p1.md) | Remoção do material da P1 deste repositório | Aceito |
| [008](008-alembic-com-sql-exportado.md) | Alembic por serviço, com SQL exportado em `db/` | Aceito |
| [009](009-expandir-e-contrair-papel-antigo.md) | Expandir agora, contrair depois: a coluna antiga de papel | Aceito |
| [010](010-esquema-do-dominio.md) | Esquema do domínio: UUID nativo, FK composta por empresa e soft delete | Aceito |
| [011](011-read-committed-nos-comandos.md) | READ COMMITTED nas transações de comando (corrida do limite de plano) | Aceito |
