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

Copie o ID do preço (começa com `price_`) do Pro e da Construtora, na página de cada produto.

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
| `STRIPE_PRICE_PRO` | ID do preço do Pro |
| `STRIPE_PRICE_CONSTRUTORA` | ID do preço da Construtora |
| `FRONTEND_URL` | `https://marcio-mazega-isw055.lapps.studio` |

| `AUTH_INTERNAL_TOKEN` | `openssl rand -hex 32` (sem ele, a Minha Conta não carrega e o e-mail de inadimplência não sai) |

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

Se a tela ficar em "Confirmando pagamento…" até o aviso de demora, veja em Developers → Webhooks a
resposta recebida: 400 é `STRIPE_WEBHOOK_SECRET` errado, 503 é variável faltando, e 500 está no log
do `api`. Teste local:
`stripe listen --forward-to localhost:8000/webhooks/stripe`.
