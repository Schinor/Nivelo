# ADR 011 — READ COMMITTED nas transações de comando

- **Status:** aceito (04/11/2026)
- **Data:** 03/11/2026
- **Complementa:** ADR 006

## Contexto

O ADR 006 decidiu que a checagem de limite de plano trava a assinatura (`SELECT ... FOR UPDATE`), conta e só então insere. Num MariaDB 11.8 de verdade, duas criações de obra simultâneas numa empresa Free **passaram as duas**:

- O isolamento padrão do InnoDB é REPEATABLE READ: a transação fixa um retrato do banco na primeira leitura. A segunda requisição espera a trava da assinatura, mas conta as obras no retrato tirado antes do commit da primeira, e vê 0.
- O MariaDB 11.8 liga `innodb_snapshot_isolation` por padrão: uma leitura com trava sobre uma linha alterada depois do retrato falha com o erro 1020 ("Record has changed since last read"), e isso virava 500.
- Uma leitura `FOR UPDATE` de uma linha que ainda não existe trava o vão do índice. A inserção feita por outra transação fica esperando até o timeout.

O SQLite dos testes não trava linha, então a suíte não via nada disso.

## Decisão

- A unidade de trabalho de Gestão de Obras abre a transação do comando em **READ COMMITTED** (só no MariaDB/MySQL). Cada comando vê o que já foi gravado, e o `FOR UPDATE` da assinatura serializa os comandos de uma mesma empresa.
- A linha de assinatura que falta (empresa anterior à Fase 3) nasce numa transação própria, também em READ COMMITTED e já gravada, antes da trava. A existência é conferida com uma leitura sem trava.
- **Escopo: só as transações de comando.** O READ COMMITTED é pedido na conexão da transação, ao abrir a unidade de trabalho, e volta ao padrão quando a conexão retorna ao pool. O engine global continua em REPEATABLE READ, e as consultas (listagens, detalhes, histórico) não passam pela unidade de trabalho, então não mudam. Um teste no MariaDB confere as duas coisas.
- `tests/test_concorrencia_mariadb.py` cobre a corrida no MariaDB e roda no CI (o passo do pytest recebe o `MARIADB_URL` do service container). Sem a correção, ele falha.

## Consequências

- Dentro de um comando, duas leituras da mesma linha podem ver valores diferentes, se outra transação gravar no meio. As regras que dependem disso (contagem do plano, versão da obra) já se protegem com a trava da assinatura e com o `WHERE versao = ?`.
- A Fase 8 (fotos e equipe) e a 4b (diários) usam a mesma unidade de trabalho e herdam o comportamento.
- Alternativa descartada: `SERIALIZABLE` no engine inteiro, que trava as leituras das listagens e aumenta os deadlocks.
