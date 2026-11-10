# Entrega da Atividade 11 — SaaS completo

> Situação em 09/11/2026 21:48 (horário de Brasília). Só está marcado o que foi conferido. Prazo: 13/11/2026.
>
> **Bloqueio:** o checkout em produção respondeu 503. O diagnóstico está em [`docs/STRIPE.md`](STRIPE.md), seção 6. Os itens que dependem de pagamento só podem ser feitos depois disso.

## Checklist

| Item | Situação | Evidência ou como fazer |
|---|---|---|
| Conta nova nasce no Free | ☐ | Print de `/assinatura` numa conta nova |
| 2ª obra ativa recusada com 402 e a mensagem do limite | ☐ | Print da tela |
| Checkout com o cartão 4242 concluído | ☐ | Bloqueado pelo 503 |
| Plano vira Pro **depois do webhook** | ☐ | Print do log com `assinatura.iniciada` antes de a tela atualizar |
| O limite some (cria a 2ª obra) | ☐ | Print da 2ª obra criada |
| Portal cancela, webhook chega e volta para o Free | ☐ | Print do portal e de `/assinatura` |
| Dashboard do Stripe em modo de teste com a assinatura | ☐ | Print, sem chaves visíveis |
| Webhook recebido em Developers → Webhooks | ☐ | Print com a resposta 200 |
| Painel admin com usuários por plano, assinaturas ativas, MRR e eventos | ☐ | Print de `/admin`, com R$ 29,90 durante a assinatura. Exige o redeploy com o painel |
| Busca por chaves do Stripe vazia (comando da Fase 11 do roteiro) | ☐ | Nenhum segredo real, mas o comando ainda acha os prefixos em `backend/app/core/config.py`, na trava que recusa chave de produção |
| `.env.example` só com os nomes | ☐ | Nenhum valor real, mas há exemplos como `sua_senha_mailtrap` e padrões como `PORT=8000` |

## O que já está comprovado por teste

Com o Stripe simulado e a assinatura real do webhook, no CI:

| Regra | Onde |
|---|---|
| Limites do Free, 402 e corrida de duas requisições | `tests/unit/test_planos.py`, `tests/test_obras_crud_api.py`, `tests/test_convites_api.py`, `tests/test_concorrencia_mariadb.py` |
| Webhook: assinatura inválida 400, repetido com um efeito só, os 4 eventos | `tests/test_assinaturas_stripe.py` |
| MRR sobe para R$ 29,90 e volta a R$ 0,00 no painel | `test_painel_admin_mostra_o_mrr_ao_assinar_e_zera_ao_cancelar` |
| Só o admin vê o painel | `tests/test_admin_api.py` |

Isso não substitui o cenário real com os cartões `4242 4242 4242 4242` e `4000 0000 0000 0341`.

## Issue de entrega

Título: `Entrega — SaaS completo`

Corpo, mencionando `@siriani`: link do commit entregue e prints acima, cada um com data e hora visíveis.
