# ADR 010 — Esquema do domínio: UUID nativo, FK composta por empresa e soft delete

- **Status:** aceito
- **Data:** 03/11/2026

## Contexto

O esquema da Fase 2 precisa cumprir a regra de tenancy (ADR 004) no próprio banco, rodar no MariaDB 11.8 de produção e no SQLite do CI, e respeitar a fronteira entre contextos (ADR 001), em que cada serviço é dono das suas tabelas.

## Decisão

- **IDs públicos em UUID v7, tipo `UUID` nativo no MariaDB** (16 bytes, disponível desde a 10.7) e `CHAR(36)` no SQLite. Um `TypeDecorator` (`UUIDNativo`) escolhe o tipo pelo dialeto; a exportação de SQL usa o dialeto `mariadb`. `usuarios.id` continua `INT` (vem do sistema herdado).
- **`empresa_id` em toda tabela de domínio**, inclusive nas que o roteiro listava sem ele (`obra_membros`, `diario_revisoes`), seguindo a regra 1 do projeto.
- **FK composta por empresa:** as tabelas filhas apontam para o pai por `(empresa_id, id)`, e não só por `id` (ex.: `diarios (empresa_id, obra_id) → obras (empresa_id, id)`). O banco recusa um diário de uma empresa ligado à obra de outra, mesmo que o código erre.
- **Sem FK entre serviços:** `empresa_id` nas tabelas da API e os `usuario_id` (autor, membro, criado_por) não têm FK para as tabelas do `auth-service`. Cada árvore de migração roda sozinha, e um contexto não depende do DDL do outro. Dentro de cada serviço, as FKs existem.
- **Soft delete de obra:** `obras.removida_em`. Uma obra removida some das listagens e não conta no limite do plano, mas o histórico de prova continua no banco. Isso cumpre o "remover" do enunciado e preserva a auditoria. Diários não têm soft delete: só o rascunho pode ser apagado, e de verdade.
- **Índices compostos começam por `empresa_id`.**
- **Concorrência otimista:** `versao` em `obras` e `diarios`.

## Consequências

- A integridade do tenant é garantida em duas camadas: no código (repositórios e rede de segurança do ORM) e no banco (FK composta).
- Sem FK entre serviços, remover uma empresa no `auth-service` não apaga em cascata os dados da API. A remoção de empresa, quando existir, é um caso de uso explícito.
- `UNIQUE (empresa_id, id)` em `obras` e `diarios` é redundante com a PK, mas é exigido pela FK composta. O custo é um índice a mais por tabela.
