# ADR 013 — O painel admin lê as contas pelo auth-service

- **Status:** proposto (09/11/2026)
- **Data:** 09/11/2026
- **Complementa:** ADR 001

## Contexto

O roteiro pede que `GET /admin/metricas` use SELECT direto. Os dados de cobrança estão na tabela `assinaturas`, que é da própria API. Já empresas, usuários e vínculos são do contexto de Identidade, e o ADR 001 diz que um contexto não lê as tabelas de outro. Empresas e usuários por plano precisam dos dois lados.

## Decisão

- A cobrança sai de um SELECT direto em `assinaturas`, numa sessão `sem_tenant` com motivo declarado.
- Contas e vínculos ativos vêm de `GET /internal/metricas/contas` do auth-service, na rede interna, com o `X-Internal-Token` que as rotas internas já usam. A resposta não traz e-mails.
- O módulo `admin` junta os dois lados na camada de aplicação. A rota fica em `/api/admin/metricas`, com o prefixo `/api` das demais.
- Se o auth-service ou o log-service não responderem, o painel continua: a cobrança aparece, e usuários ou eventos vêm nulos, com aviso na tela.
- Os gauges `nivelo_mrr_centavos` e `nivelo_assinaturas_ativas` são lidos do banco a cada coleta, então valem com qualquer número de processos.

## Consequências

- A fronteira entre contextos continua valendo, e o `import-linter` ganha um contrato para as camadas do `admin`.
- O painel depende de `AUTH_INTERNAL_TOKEN` para mostrar usuários e nomes.
- Cada abertura do painel lê todas as empresas e contas. Serve para o volume atual; com muitas empresas, a rota interna deve devolver contagens prontas.
- Alternativa descartada: `JOIN` com `usuarios` e `vinculos` na API. Seria uma consulta só, mas ligaria a API ao esquema de Identidade.
