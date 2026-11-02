# ADR 001 — Contextos delimitados

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

O Nivelo nasce de uma stack que já está no ar, com quatro serviços de aplicação e um limite rígido de infraestrutura: nenhum container novo, nenhuma porta publicada nova e 1 GB de RAM por container. O produto, porém, tem partes com ritmos de mudança diferentes: identidade, obras e diários, cobrança e auditoria.

## Decisão

| Contexto | Tipo | Onde roda |
|---|---|---|
| Identidade e Acesso | genérico | `auth-service` (rede interna) |
| Gestão de Obras | **núcleo** | serviço `api` |
| Assinaturas | suporte | módulo `assinaturas` dentro do serviço `api` |
| Auditoria | genérico | `log-service` + Redis Streams |
| Arquivos | infraestrutura | adaptador S3 para o Garage |

- Um contexto não lê as tabelas de outro. A Gestão de Obras conhece o usuário pelo `UsuarioId` e pelos claims do JWT, sem `JOIN` com `usuarios`.
- Assinaturas não ganha container: é um pacote separado dentro da API, com a fronteira garantida pelo `import-linter`.
- O Stripe entra por uma camada anticorrupção (`assinaturas/infrastructure/stripe_gateway.py`). O resto do código fala `Plano`, `StatusAssinatura` e `EmpresaId`.

## Consequências

- O núcleo (obras e diários) evolui sem depender do formato do Stripe nem das tabelas de identidade.
- Assinaturas compartilha processo e banco com a API, então uma falha grave nela afeta a API. Se um dia isso pesar, a fronteira de pacote já existe para virar serviço.
- Consultas que cruzam contextos (ex.: o painel admin) são feitas por leitura dedicada, não por `JOIN` dentro do domínio.
