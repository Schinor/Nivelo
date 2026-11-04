# ADR 012 — O relay da outbox entrega os eventos ao log-service por HTTP

- **Status:** proposto (aguardando revisão)
- **Data:** 04/11/2026
- **Complementa:** ADR 003

## Contexto

O ADR 003 diz que o relay "publica no Redis Stream do log-service". Há dois jeitos de fazer isso: a API escrever direto no Redis (`XADD audit:events`), ou entregar o lote ao log-service, que escreve no stream. A API e o Redis estão na mesma rede da stack, então os dois jeitos funcionam sem mudar a infraestrutura.

## Decisão

- O relay entrega o lote por HTTP, na rede interna, em `POST /eventos/negocio` do log-service, com o mesmo `X-Internal-Token` que os eventos técnicos já usam.
- O log-service é o único que escreve no stream. Ele guarda uma marca por `event_id` (`SET audit:evento:<id> NX`, 30 dias) e ignora o evento repetido. Se o `XADD` falhar, apaga a marca e responde 503, e o relay reenvia o lote no próximo ciclo.
- O evento entra no stream achatado: os campos antigos (`acao`, `usuario_id`, `timestamp`, `recurso`) continuam preenchidos, para a listagem do admin seguir funcionando, e `obra_id` fica no topo, para o histórico da obra filtrar (`GET /eventos?empresa_id=&obra_id=`).
- O relay é uma task asyncio no `lifespan` da API. A cada 1 s, numa thread, lê até 100 pendentes com `FOR UPDATE SKIP LOCKED`, publica e marca `publicado_em`. Se falhar, soma `tentativas` e tenta de novo.

## Consequências

- A API não ganha a dependência `redis` nem a variável `REDIS_URL`, e o formato do stream fica num lugar só.
- Se o log-service cair, os eventos esperam na outbox. Nada se perde, só atrasa. O `/health/ready` da API continua sem depender do log-service.
- A entrega é "pelo menos uma vez" de ponta a ponta. A marca por `event_id` deixa o stream sem repetição.
- Com mais de um processo da API, o `SKIP LOCKED` evita que dois relays peguem as mesmas linhas.
- A outbox cresce sem limpeza. Uma limpeza das linhas publicadas há mais de 30 dias fica para a Fase 12.
- Alternativa descartada: `XADD` direto da API. Seria um salto a menos, mas duplicaria o formato do stream e a deduplicação nos dois serviços.
