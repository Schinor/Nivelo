# ADR 006 — 402 Payment Required para limite de plano

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

O plano Free tem limites (1 obra ativa, 30 fotos por obra, 2 pessoas na equipe). Quando a ação passa do limite, a resposta precisa ser diferente de "sem permissão" (403): o usuário pode fazer a ação, só precisa de outro plano. O front precisa reconhecer esse caso para mostrar "Assinar Pro" em vez de uma mensagem de erro.

## Decisão

- Estourar o limite responde **402 Payment Required** em Problem Details, com `type: https://nivelo/erros/plano-limite-excedido` e os campos `limite`, `atual`, `plano_atual`, `plano_sugerido` e `acao`.
- Os direitos são calculados no domínio (`direitos_efetivos(plano, status)`), e o plano pago só vale com status `active` ou `trialing`; nos demais, a empresa recebe os direitos do Free.
- A checagem não tem corrida: o handler faz `SELECT ... FOR UPDATE` na linha da assinatura, conta, aplica a `PoliticaDePlano` e só então insere.
- O plano é consultado no banco a cada requisição e só muda pelo webhook do Stripe, nunca pelo redirect do checkout.

## Consequências

- O front trata o 402 por `type` e abre o modal de upgrade.
- O 402 é pouco usado na web; clientes genéricos o tratam como um 4xx comum, o que é aceitável.
- O `FOR UPDATE` serializa as ações que contam contra o limite de uma mesma empresa. Para o volume de um pequeno empreiteiro, o custo é desprezível.
