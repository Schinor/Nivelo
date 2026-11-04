# ADR 012 — O relay da outbox entrega os eventos ao log-service por HTTP

- **Status:** aceito (04/11/2026)
- **Data:** 04/11/2026
- **Complementa:** ADR 003

## Contexto

O ADR 003 diz que o relay "publica no Redis Stream do log-service". Há dois jeitos de fazer isso: a API escrever direto no Redis (`XADD audit:events`), ou entregar o lote ao log-service, que escreve no stream. A API e o Redis estão na mesma rede da stack, então os dois jeitos funcionam sem mudar a infraestrutura.

## Decisão

- O relay entrega o lote por HTTP, na rede interna, em `POST /eventos/negocio` do log-service, com o mesmo `X-Internal-Token` que os eventos técnicos já usam.
- O log-service é o único que escreve no stream. Ele guarda uma marca por `event_id` (`SET audit:evento:<id> NX`, 30 dias) e ignora o evento repetido. Se o `XADD` falhar, apaga a marca e responde 503, e o relay reenvia o lote no próximo ciclo.
- O evento entra no stream achatado: os campos antigos (`acao`, `usuario_id`, `timestamp`, `recurso`) continuam preenchidos, para a listagem do admin seguir funcionando, e `obra_id` fica no topo, para o histórico da obra filtrar (`GET /eventos?empresa_id=&obra_id=`).
- **Token interno:** o lote vai com `X-Internal-Token` (`LOG_INTERNAL_TOKEN`, o mesmo valor nos dois serviços, só nas variáveis da stack). O log-service compara em tempo constante, responde 401 sem ele e não sobe com o token vazio.
- **Entrega em lotes:** o relay é uma task asyncio no `lifespan` da API. A cada 1 s, numa thread, lê até 100 pendentes prontos com `FOR UPDATE SKIP LOCKED`, na ordem em que aconteceram (`ocorrido_em` e o `event_id`, UUID v7 monotônico), publica o lote numa chamada só e marca `publicado_em`.
- **Backoff com tentativas, por linha:** cada falha soma `tentativas`, guarda o `ultimo_erro` e adia a linha (`proxima_tentativa_em`) em 1 s, 2 s, 4 s, ... até 5 min. A linha nunca é descartada.
  - Queda, 5xx ou token recusado (401): o lote inteiro espera.
  - Conteúdo recusado (400, 413 ou 422): o relay tenta os eventos um a um, e só o recusado fica para trás. Um evento ruim não trava a fila; ele sai da ordem, e o `ultimo_erro` diz por quê.

## Consequências

- A API não ganha a dependência `redis` nem a variável `REDIS_URL`, e o formato do stream fica num lugar só.
- Se o log-service cair, os eventos esperam na outbox, com backoff de até 5 min. Nada se perde, só atrasa. O `/health/ready` da API continua sem depender do log-service.
- A entrega é "pelo menos uma vez" de ponta a ponta. A marca por `event_id` deixa o stream sem repetição.
- Com mais de um processo da API, o `SKIP LOCKED` evita que dois relays peguem as mesmas linhas.
- A outbox cresce sem limpeza. Uma limpeza das linhas publicadas há mais de 30 dias fica para a Fase 12.
- Alternativa descartada: `XADD` direto da API. Seria um salto a menos, mas duplicaria o formato do stream e a deduplicação nos dois serviços.
