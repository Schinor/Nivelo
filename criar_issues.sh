#!/usr/bin/env bash
# Cria o backlog da Atividade 9 no repositório novo.
# Uso: rode dentro da pasta do repositório clonado, com o gh autenticado (gh auth login).
set -e

gh label create "atividade-10" --color 1D76DB --description "Negócio no ar" 2>/dev/null || true
gh label create "atividade-11" --color 5319E7 --description "Assinatura com Stripe" 2>/dev/null || true

gh issue create --label atividade-10 --title "Modelar as tabelas de empresas, obras, diários e fotos" \
  --body "Criar empresas, obras, diarios, diario_fotos, ocorrencias e obra_clientes no MariaDB, com empresa_id em todas as tabelas do domínio. Remover favoritos/comentários do domínio antigo."

gh issue create --label atividade-10 --title "Multi-tenancy: isolar dados por empresa_id" \
  --body "empresa_id vem do JWT, nunca do corpo ou da URL. Teste: usuário da empresa A recebe 404 ao pedir obra da empresa B."

gh issue create --label atividade-10 --title "Criar os papéis dono, encarregado e cliente no RBAC" \
  --body "Substituir os papéis temáticos do HANK+. Documentar no README a matriz do que cada papel pode fazer e aplicar no backend (403)."

gh issue create --label atividade-10 --title "Fluxo de convite de encarregado e de cliente por e-mail" \
  --body "Dono convida por e-mail; link com token de uso único e expiração, reaproveitando a lógica de reset_tokens."

gh issue create --label atividade-10 --title "Registrar diário do dia com fotos no Garage" \
  --body "Tela mobile-first: data, clima, atividades, ocorrências e fotos. Fotos no Garage com URL pré-assinada."

gh issue create --label atividade-10 --title "Eventos de auditoria do diário no log-service" \
  --body "diario.registrado, diario.editado, foto.enviada, cliente.visualizou. Histórico visível na obra."

gh issue create --label atividade-10 --title "Landing page do Nivelo" \
  --body "Página pública com a proposta de valor, os planos Free/Pro e botão de cadastro."

gh issue create --label atividade-10 --title "Trocar a stack do Portainer para o repositório novo" \
  --body "Mesmo subdomínio e mesmos serviços; apontar build/deploy (GHCR) para este repositório."

gh issue create --label atividade-11 --title "Plano Pro no Stripe com assinatura recorrente" \
  --body "Produtos Free (R\$ 0) e Pro (R\$ 59/mês) em modo de teste; checkout com mode=subscription; customer guardado na empresa."

gh issue create --label atividade-11 --title "Webhooks de assinatura e portal do cliente" \
  --body "checkout.session.completed, customer.subscription.updated/deleted, invoice.payment_failed com validação e idempotência; botão Gerenciar assinatura."

gh issue create --label atividade-11 --title "Limites do Free na API e painel admin" \
  --body "Free: 1 obra ativa e 3 diários/mês, barrado no backend com mensagem clara. Painel admin: usuários por plano, assinaturas ativas, MRR de teste, últimos eventos."

echo "Backlog criado."