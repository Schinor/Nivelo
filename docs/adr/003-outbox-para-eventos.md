# ADR 003 — Outbox transacional para os eventos de auditoria

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

Hoje a API envia o evento de auditoria ao `log-service` por HTTP, em segundo plano, com timeout de 1,5 s. Se o `log-service` ou o Redis estiverem fora, o evento se perde em silêncio. Para um produto cujo valor é o histórico de prova, perder "quem publicou o diário e quando" não é aceitável.

## Decisão

1. O agregado acumula os eventos de domínio em memória.
2. O `UnitOfWork.commit()` grava o agregado **e** os eventos na tabela `outbox`, na mesma transação do MariaDB.
3. Um relay (`asyncio` task dentro da própria API, sem container novo) lê a `outbox` a cada 1 s, publica no Redis Stream do `log-service` e marca `publicado_em`.
4. Todo evento tem o mesmo formato, com `event_id`, `tipo`, `empresa_id`, `ator_id`, `ator_papel`, `recurso`, `recurso_id`, `ocorrido_em`, `request_id` e `dados`. O `event_id` torna o consumo idempotente.

## Consequências

- Se o dado foi gravado, o evento também foi. A publicação pode atrasar, mas não se perde.
- A entrega é "pelo menos uma vez": o consumidor precisa ignorar `event_id` repetido.
- O relay roda dentro da API; com mais de uma réplica, ele precisaria de trava (`SELECT ... FOR UPDATE SKIP LOCKED`). Hoje há uma réplica só.
- Os eventos técnicos herdados (login, logout, `acesso_negado`) continuam pelo caminho direto até migrarem.
