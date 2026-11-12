# Configuração do Stripe

Tudo em **modo de teste** (a API recusa chave de produção no boot). Chaves e segredos ficam só nas
variáveis da stack no Portainer, nunca no repositório.

Quem muda o plano é só o webhook. Voltar do checkout não altera nada: a tela `/assinatura` aguarda a
confirmação consultando a API.

## 1. Produtos e preços

Em **Product catalog → Add product**, com moeda BRL e cobrança recorrente mensal:

| Produto | Preço | Imagem |
|---|---|---|
| Nivelo Free | R$ 0,00/mês | `docs/stripe/nivelo-free.png` |
| Nivelo Pro | R$ 29,90/mês | `docs/stripe/nivelo-pro.png` |
| Nivelo Construtora | R$ 69,90/mês | `docs/stripe/nivelo-construtora.png` |

A imagem é enviada no campo **Image** do produto e aparece no Checkout. Use o PNG: os `.svg` da mesma
pasta são a fonte editável, e o Stripe não os aceita como imagem de produto.

Copie o ID do **preço** do Pro e da Construtora: na página do produto, seção **Pricing**, abra o
preço mensal e use o ID que começa com `price_`. O ID que aparece no topo da página do produto
começa com `prod_` e **não serve**: com ele o checkout responde 503 (seção 6).

## 2. Portal do cliente

Em **Settings → Billing → Customer portal**:

- permita trocar de plano entre Pro e Construtora;
- permita o cancelamento **imediato** (para o teste);
- defina o link de retorno como `https://marcio-mazega-isw055.lapps.studio/assinatura`;
- salve as alterações do modo de teste.

## 3. Webhook

Em **Developers → Webhooks → Add destination**:

- URL: `https://marcio-mazega-isw055.lapps.studio/webhooks/stripe` (sem a porta 8220: o Stripe entra
  pelo domínio público);
- eventos: `checkout.session.completed`, `customer.subscription.updated`,
  `customer.subscription.deleted` e `invoice.payment_failed`.

Depois de criar, copie o **Signing secret** do destino.

## 4. Variáveis da stack

| Variável | Valor |
|---|---|
| `STRIPE_SECRET_KEY` | Developers → API keys → Secret key (a de teste) |
| `STRIPE_WEBHOOK_SECRET` | Signing secret do passo 3 |
| `STRIPE_PRICE_PRO` | ID do preço do Pro (`price_...`, nunca `prod_...`) |
| `STRIPE_PRICE_CONSTRUTORA` | ID do preço da Construtora (`price_...`, nunca `prod_...`) |
| `FRONTEND_URL` | `https://marcio-mazega-isw055.lapps.studio` |
| `AUTH_INTERNAL_TOKEN` | `openssl rand -hex 32` (sem ele, a Minha Conta não carrega, o e-mail de inadimplência não sai e o painel admin fica sem usuários) |

A variável antiga `STRIPE_PRICE_ID` não é mais usada e pode sair da stack. Sem qualquer uma das quatro
variáveis `STRIPE_*`, o checkout e o webhook respondem 503.

Antes do **Pull and redeploy**, faça o dump do banco (`docs/DEPLOY.md`, passo 0): a migração
`008_remove_premium` apaga as colunas e a tabela do premium antigo.

## 5. Teste

| Cartão | Resultado |
|---|---|
| `4242 4242 4242 4242` | pagamento aprovado |
| `4000 0000 0000 0341` | anexa, mas a cobrança falha (provoca `invoice.payment_failed`) |

Data futura qualquer e CVC qualquer. O caminho completo, como dono de uma empresa:

1. **Assinatura → Assinar Pro** abre o Checkout. Pague com o cartão aprovado.
2. A tela volta com "Confirmando pagamento…" e passa para o Pro quando o webhook chegar.
3. Em Developers → Webhooks, o evento aparece com resposta 200.
4. **Gerenciar assinatura** abre o portal. Cancele: a empresa volta para o Free.
5. No **Painel** do admin (`/admin`), o MRR de teste mostra R$ 29,90 enquanto a assinatura está
   ativa e volta a R$ 0,00 depois do cancelamento.

Se a tela ficar em "Confirmando pagamento…" até o aviso de demora, veja em Developers → Webhooks a
resposta recebida: 400 é `STRIPE_WEBHOOK_SECRET` errado, 503 é variável faltando, e 500 está no log
do `api`. Teste local:
`stripe listen --forward-to localhost:8000/webhooks/stripe`.

## 6. Se o checkout responder 503

A resposta "Não foi possível falar com o meio de pagamento" quer dizer que o Stripe recusou a
chamada ou não foi alcançado. "Pagamentos não configurados neste ambiente" é outra coisa: falta uma
das variáveis `STRIPE_*`.

Em **Containers → api → Logs**, procure `Stripe recusou a chamada`. A linha traz o tipo do erro, o
status HTTP, o código, o campo recusado e a mensagem do Stripe.

| No log | Causa provável | O que fazer |
|---|---|---|
| `campo=line_items[0][price]` ou `No such price` | O ID é de produto (`prod_`), ou o preço é de outra conta ou de outro modo | Copie o ID que começa com `price_`, com o painel em modo de teste, na conta da chave |
| Mensagem sobre `recurring price` ou modo `subscription` | O preço foi criado como pagamento único | Crie um preço recorrente mensal e troque a variável |
| `campo=success_url` ou `Not a valid URL` | `FRONTEND_URL` vazia ou sem `https://` | Use a URL pública completa |
| `campo=customer` ou `No such customer` | A empresa guardou um cliente de outra conta do Stripe | Limpe o `stripe_customer_id` dessa empresa |
| `AuthenticationError` | Chave errada, revogada ou colada com espaço | Copie a Secret key de teste de novo |
| `PermissionError` | Chave restrita sem permissão | Use a Secret key padrão |
| `APIConnectionError` | O container não alcança `api.stripe.com` | Verifique a saída de rede do host |
| `IdempotencyError` | O nome ou o e-mail do dono mudou entre tentativas em menos de 24 h | Espere 24 h ou teste com outra empresa |

Caso real (12/11/2026): o log mostrou
`InvalidRequestError http=400 codigo=resource_missing campo=line_items[0][price]: No such price: 'prod_...'`.
A variável do preço estava com o ID do produto. Com os IDs `price_` nas duas variáveis e o redeploy,
o checkout passou a abrir.

Depois de corrigir uma variável, faça **Pull and redeploy**: o container só recebe o valor novo ao
ser recriado.
