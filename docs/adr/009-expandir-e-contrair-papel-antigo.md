# ADR 009 — Expandir agora, contrair depois: a coluna antiga de papel

- **Status:** aceito
- **Data:** 03/11/2026

## Contexto

O modelo novo de identidade (ADR 004) tira o papel de negócio de `usuarios` e o põe em `vinculos`. O roteiro manda remover a coluna antiga de papel na Fase 2 (modelo de dados). Mas o código que lê o papel (JWT, painel de usuários, `/api/logs`, matriz de permissões em `roles`, `permissions`, `role_permissions` e `user_permissions`) só é trocado na Fase 3. Remover a coluna na Fase 2 deixaria o login e o painel quebrados entre as duas fases.

## Decisão

Usar o padrão *expandir e contrair* (expand/contract):

- **Fase 2 (expandir):** criar `empresas`, `vinculos`, `convites` e `usuarios.admin_plataforma`, e converter os dados que já têm destino (`role = 'admin'` vira `admin_plataforma = true`). Nada é removido; o código antigo continua funcionando.
- **Fase 3 (contrair):** no mesmo commit em que o código passa a usar vínculos e `admin_plataforma`, uma revisão nova remove `usuarios.role`, `usuarios.role_id` e as tabelas `roles`, `permissions`, `role_permissions` e `user_permissions`.

Usuários existentes que não são admin ficam sem vínculo. No primeiro login depois da Fase 3, eles entram e criam a própria empresa (`POST /auth/empresas`), como prevê o roteiro para e-mail já cadastrado.

## Consequências

- O sistema fica de pé entre as fases, e cada deploy é seguro sozinho.
- Por um intervalo curto o banco tem as duas formas (coluna antiga e vínculos). A revisão de contração na Fase 3 é obrigatória e entra no checklist dela.
- A conversão de admin é idempotente e roda de novo sem efeito.
