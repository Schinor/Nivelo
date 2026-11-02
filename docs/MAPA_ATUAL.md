# Mapa atual — o HANK+ antes da troca para o Nivelo

> Retrato do repositório em 02/11/2026 (commit `9ff7a38`), feito na Fase 0 do roteiro, sem alterar código de aplicação.
> Serve de base para as Fases 1 a 9. **Na Fase 1** o domínio antigo saiu do código; aqui os nomes dele foram trocados por descrições (regra 8), e a seção 13 resume o que mudou.

## 1. Respostas da verificação

| Pergunta | Resposta |
|---|---|
| **(a)** O serviço `catalogo` pode virar `api` sem quebrar labels, proxy ou variáveis da stack? | **Sim. Confirmado em 02/11:** o túnel do `lapps.studio` aponta para a **porta publicada no host** (`${PORT}`), não para o nome do container. O compose não tem `labels`. O nome `catalogo` só aparece em `prometheus/prometheus.yml` (alvo `catalogo:8000`), no `depends_on` do Prometheus e no `--forward-to` da Stripe CLI no `docker-compose.dev.yml`; os três mudam junto. O `container_name` também pode mudar. As variáveis da stack não dependem do nome do serviço. |
| **(b)** MariaDB ou MySQL, e qual versão? | **MariaDB 11.8.8**, compartilhado e fora da stack (confirmado em 02/11 com `SELECT VERSION()`). Tem o tipo `UUID` nativo (desde a 10.7), que os IDs de domínio vão usar na Fase 2. `JSON` é alias de `LONGTEXT` com `CHECK (JSON_VALID(...))`; `SELECT ... FOR UPDATE` e `INSERT IGNORE` funcionam. |
| **(c)** Storage em uso | **Garage v2.3.0** (`dxflrs/garage`), nó único (`--single-node --default-bucket`), API S3 na porta interna 3900, bucket `catalogo-avatares` (`STORAGE_BUCKET`). O navegador acessa pela ponte `/storage/*` do catálogo. Não há MinIO. |
| **(d)** Como o Stripe está hoje | Ver §7. Resumo: **quem fala com o Stripe é o `catalogo`** (checkout e webhook em `POST /webhooks/stripe`); **quem grava o status é o `auth-service`** (`POST /internal/premium/eventos`, colunas `premium` em `usuarios`, tabela `stripe_eventos_processados`). Fica intocado até a Fase 9. |

## 2. Serviços e portas

| Serviço (compose) | Container | Imagem GHCR | Porta | Responsabilidade |
|---|---|---|---|---|
| `catalogo` | (nome antigo do container) | `ghcr.io/schinor/catalogo-*` | `${PORT:-8000}:8000` — **única publicada** | FastAPI + SPA Angular embutida; API do catálogo, favoritos, comentários, perfis, premium e logs; ponte para auth, Garage, Grafana e Prometheus |
| `auth-service` | `auth-service-schinor` | `ghcr.io/schinor/auth-service` | `expose: 8001` | Usuários, JWT, RBAC, reset de senha, status premium |
| `log-service` | `log-service-schinor` | `ghcr.io/schinor/log-service` | `expose: 8002` | Recebe e lista eventos de auditoria (Redis Stream) |
| `redis` | (automático) | `redis:7-alpine` | nenhuma | Stream `audit:events` (AOF ligado) |
| `garage` | `garage-schinor` | `ghcr.io/schinor/garage` | `expose: 3900` | Object storage S3 |
| `prometheus` | (automático) | `ghcr.io/schinor/prometheus` | `expose: 9090` | Scrape de `/metrics` dos 3 serviços Python |
| `grafana` | (automático) | `ghcr.io/schinor/grafana` | `expose: 3000` | Painel do projeto anterior |

- Rede: (nome antigo, temático), bridge com sub-rede fixa `10.20.30.0/28` (o pool do host compartilhado está esgotado).
- Volumes: `redis-data`, `grafana-data`, `garage-meta`, `garage-data`.
- **Nenhum container tem `mem_limit`.** A regra de 1 GB por container (Fase 6) ainda precisa entrar no compose.
- Health checks: `catalogo`, `auth-service`, `log-service`, `redis` e `garage` têm; `prometheus` e `grafana` não.
- Compose de dev (`docker-compose.dev.yml`): build local, rede de dev própria, publica 9090 e 3000, e tem a `stripe-cli` atrás do profile `stripe`.
- Compose de CI (`docker-compose.ci.yml`): SQLite descartável em cada serviço, segredos gerados no workflow.

## 3. Variáveis de ambiente

| Variável | catalogo | auth | log | outros | Observação |
|---|---|---|---|---|---|
| `DATABASE_URL` | ✅ | ✅ | | | Mesmo banco, tabelas diferentes |
| `SECRET_KEY`, `ALGORITHM` | ✅ | ✅ | | | JWT HS256 compartilhado |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | ✅ | | | Hoje **1440** (24 h); o roteiro pede 15 min |
| `PORT` | ✅ | | | | Porta publicada no host |
| URL e chave da API externa do catálogo | ✅ | | | | **Saíram na Fase 1** |
| `AUTH_SERVICE_URL` | ✅ | | | | Fixa no compose: `http://auth-service-schinor:8001` |
| `LOG_SERVICE_URL`, `LOG_INTERNAL_TOKEN` | ✅ | | ✅ | | Token interno catálogo → log |
| `GRAFANA_INTERNAL_URL`, `PROMETHEUS_INTERNAL_URL`, `PROMETHEUS_PROXY_PASSWORD` | ✅ | | | | Pontes de observabilidade |
| `STORAGE_ENDPOINT`, `STORAGE_REGION`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY` | ✅ | | | garage | O Garage recebe as mesmas chaves como `GARAGE_DEFAULT_*` |
| `STORAGE_BANDA_MINIMA_KBPS`, `STORAGE_MARGEM_USO_SEGUNDOS`, `STORAGE_EXPIRACAO_MAX_SEGUNDOS`, `PERFIL_FOTO_MAX_BYTES` | ✅ | | | | Expiração da URL pré-assinada e tamanho da foto de perfil |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID` | ✅ | | | | Recusa `sk_live_` no boot |
| `FRONTEND_URL` | ✅ | | | | Retorno do checkout |
| `LIMITE_FAVORITOS_FREE` | ✅ | | | | Limite do Free do HANK+ (5 favoritos) |
| `AUTH_INTERNAL_TOKEN` | ✅ | ✅ | | | Token catálogo → `/internal/premium` |
| `MAILTRAP_*` (`HOST`, `PORT`, `USERNAME`, `PASSWORD`, `FROM_EMAIL`, `FROM_NAME`) | | ✅ | | | Remetente padrão era o do projeto anterior (trocado na Fase 1) |
| `CATALOGO_URL` | | ✅ | | grafana | Link do e-mail de reset e `GF_SERVER_ROOT_URL` |
| `RESET_TOKEN_EXPIRE_MINUTES`, `RESET_REQUEST_LIMIT`, `RESET_REQUEST_WINDOW_MINUTES`, `EMAIL_LOG_LINK_WITHOUT_SMTP` | | ✅ | | | Reset de senha |
| `REDIS_URL` | | | ✅ | | Fixa no compose |
| `GARAGE_RPC_SECRET` | | | | garage | |
| `GRAFANA_ADMIN_PASSWORD` | | | | grafana | |
| `IMAGE_TAG` | | | | todos | `latest` ou `sha-<commit>` |

Novas, a entrar no `.env.example` (só o nome) nas fases seguintes: `ADMIN_EMAIL`, `ADMIN_SENHA_INICIAL`, `SEED`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_CONSTRUTORA`, `APP_BASE_URL`.

## 4. Banco: tabelas e migrações

Todas no mesmo MariaDB. **IDs são `INT AUTO_INCREMENT`** (o roteiro pede UUID nos recursos de domínio).

| Tabela | Dono | Colunas principais |
|---|---|---|
| `usuarios` | auth | `id`, `nome`, `email` (único), `senha_hash` (bcrypt), `role` (slug), `role_id` FK `roles`, `criado_em`, `premium`, `stripe_customer_id`, `stripe_subscription_id`, `premium_desde` |
| `roles` | auth | `id`, `name`, `slug` (único), `description` |
| `permissions` | auth | `id`, `action`, `resource`, `description` (permissão = `action:resource`) |
| `role_permissions` | auth | `role_id`, `permission_id` |
| `user_permissions` | auth | `usuario_id`, `permission_id`, `concedida` (concessão ou revogação individual) |
| `reset_tokens` | auth | `id`, `token` (128, **guardado em claro**), `usuario_id`, `criado_em`, `expira_em`, `usado` |
| `stripe_eventos_processados` | auth | `event_id` PK, `tipo`, `processado_em` |
| `favoritos` | catalogo | `id`, `usuario_id`, id do item externo, `titulo`, imagem, `criado_em` (**removida na Fase 1**) |
| `comentarios` | catalogo | `id`, `usuario_id`, id do item externo, `texto`, `criado_em` (**removida na Fase 1**) |
| `perfis` | catalogo | `usuario_id` PK, `bio`, `foto_key`, `foto_bytes`, `atualizado_em` |

**Como o esquema é criado hoje:**
- **catalogo:** `Base.metadata.create_all()` no import do `main.py`. Sem migração.
- **auth-service:** `create_all()` + `ALTER TABLE` condicionais em `init_db()` no boot, mais o seed do RBAC (`rbac_seed.py`). Há também 4 migrações Alembic (`001_add_role_and_reset_tokens` a `004_add_premium_stripe`), que **não rodam no boot**: só manualmente com `alembic upgrade head`.
- Não há tabela `schema_migrations` nem pasta `db/`.

## 5. Rotas

### catalogo (público, via `${PORT}`)

| Grupo | Rotas | Auth |
|---|---|---|
| Auth (ponte) | `POST /api/auth/cadastro`, `/login`, `/logout`, `GET /me`, `POST /forgot-password`, `GET /validate-reset-token/{token}`, `POST /reset-password` | pública, exceto `logout` e `me` |
| Admin (ponte) | `GET /api/auth/users`, `PUT /users/{id}/role`, `PUT /users/{id}/permissions`, `DELETE /users/{id}`, `GET/POST /roles`, `GET /permissions`, `GET /admin/status`, `GET /users/{id}/role` | JWT + permissão |
| Catálogo | listagem e detalhe dos itens da API externa | pública (**removidas na Fase 1**) |
| Favoritos | `GET/POST /api/favoritos`, `DELETE /api/favoritos/{id}` | JWT + permissão (**removidas na Fase 1**) |
| Comentários | `GET /api/comentarios`, `GET /api/comentarios/{id}`, `POST`, `DELETE /{id}` | JWT + permissão (**removidas na Fase 1**) |
| Perfis | `GET /api/perfis/me`, `GET/PUT /api/perfis/{id}`, `PUT/DELETE /api/perfis/{id}/foto` | JWT |
| Premium | `GET /api/premium/status`, `POST /api/premium/checkout` | JWT |
| Webhook | `POST /webhooks/stripe` | `Stripe-Signature` |
| Auditoria | `GET /api/logs` | JWT + `visualizar:logs` |
| Infra | `/health`, `/metrics`, `/storage/*`, `/grafana/*`, `/prometheus/*` (Basic), `/api/docs`, `/api/redoc`, SPA em `/{path}` | variada |

O `/health` do catálogo já é de prontidão (banco + auth + Garage, 503 se algum cair). Não existe `/health/live` nem `/health/ready`.

### auth-service (rede interna, porta 8001)

`POST /cadastro`, `POST /login`, `GET /me`, `POST /forgot-password`, `GET /validate-reset-token/{token}`, `POST /reset-password`, `GET /users`, `GET /users/{id}`, `GET /users/{id}/role`, `PUT /users/{id}/role`, `PUT /users/{id}/permissions`, `DELETE /users/{id}`, `GET/POST /roles`, `GET /permissions`, `GET /admin/status`, `POST /internal/premium/eventos` (`X-Internal-Token`), `GET /health`, `/metrics`.

### log-service (rede interna, porta 8002)

`POST /eventos` (202, `X-Internal-Token`), `GET /eventos?limit=` (mais recentes primeiro, até 500), `GET /health`, `/metrics`.

## 6. JWT, RBAC e auditoria

**Fluxo do JWT (Padrão B já em uso):**
1. O navegador faz `POST /api/auth/login` (form OAuth2) no catálogo, que repassa ao auth-service.
2. O auth-service confere o bcrypt e assina um HS256 com `sub` (id INT), `email`, `nome`, `role` (slug) e `permissions` (lista `acao:recurso`), validade de `ACCESS_TOKEN_EXPIRE_MINUTES`.
3. O catálogo decodifica localmente com a mesma `SECRET_KEY` (`dependencies.current_user`); se falhar, tenta `GET /me` no auth-service.
4. `require_permission("acao:recurso")` libera se a permissão está no token ou se há `administrar:sistema`.
5. **Não há refresh token.** O logout só registra o evento (JWT stateless).
6. Não há `empresa_id` nem conceito de tenant.

**RBAC atual:** granular por permissão, com quatro papéis temáticos do projeto anterior e o `admin` criados pelo `rbac_seed.py` a cada boot. O papel padrão do cadastro é `amigo-do-wilson`. Sai na Fase 1, e os papéis `admin`, `dono`, `encarregado` e `cliente` entram na Fase 3.

**Auditoria:**
- O catálogo chama `log_client.registrar(acao, ...)`, que faz `POST /eventos` no log-service com timeout de 1,5 s, quase sempre como `BackgroundTask`. Se falhar, só gera um warning e **o evento se perde** (é o problema que o outbox da Parte A.4 resolve).
- Formato atual: `usuario_id`, `acao`, `origem`, `timestamp`, `recurso`, `detalhes`, `ip`. Gravado no stream `audit:events` com `XADD maxlen≈100 000`.
- Todo 403 do catálogo passa pelo handler global `auditar_403`, que registra `acesso_negado`.
- Erros da API saem no formato padrão do FastAPI (`{"detail": ...}`), não em Problem Details.

## 7. Stripe hoje (fica intocado até a Fase 9)

| Item | Onde | Detalhe |
|---|---|---|
| Checkout | `catalogo` → `POST /api/premium/checkout` | `services/pagamentos.py`: `mode=subscription`, um `STRIPE_PRICE_ID` (Premium R$ 9,90/mês), `client_reference_id = usuario_id`, retorno em `FRONTEND_URL/premium/sucesso` e `/premium/cancelado`. 409 se já é premium. |
| Status | `catalogo` → `GET /api/premium/status` | Lê `premium` do auth-service (`GET /users/{id}`), nunca do JWT, e devolve o uso de **favoritos** contra `LIMITE_FAVORITOS_FREE`. |
| Webhook | `catalogo` → `POST /webhooks/stripe` | Corpo bruto + `construct_event`. Trata `checkout.session.completed` (só `mode=subscription` pago) e `customer.subscription.deleted`. Repassa só os IDs ao auth-service. Audita `premium_ativado` e `premium_cancelado`. |
| Gravação | `auth-service` → `POST /internal/premium/eventos` | Idempotência por `event_id` em `stripe_eventos_processados`, na mesma transação da mudança em `usuarios`. `IntegrityError` em entrega concorrente vira "duplicado". |
| Campos | `usuarios` | `premium` (bool), `stripe_customer_id`, `stripe_subscription_id`, `premium_desde`. A assinatura é **por usuário**, não por empresa. |
| URL do webhook cadastrada no Stripe | painel do Stripe | Pelo código e pela documentação: `https://marcio-mazega-isw055.lapps.studio/webhooks/stripe`. **Confirme no painel** (Developers → Webhooks). Na Fase 9 ela muda para `/api/assinaturas/webhook`. |
| Variáveis | catalogo | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`, `FRONTEND_URL`, `LIMITE_FAVORITOS_FREE`, `AUTH_INTERNAL_TOKEN` (também no auth). |
| Eventos ainda não tratados | — | `customer.subscription.updated` e `invoice.payment_failed`, e o portal do cliente (Fase 9). |

**Atenção para a Fase 1:** o `GET /api/premium/status` conta **favoritos**. Ao remover favoritos, essa rota precisa perder a contagem (sem mexer no fluxo do Stripe), e os testes de `tests/test_premium.py` que dependem de favoritos precisam ser ajustados.

## 8. Deploy

- **GitHub Actions** (`.github/workflows/ci-cd.yml`): no push para `main` e em PR, roda o `pytest -q` (102 testes passando hoje) e sobe o `docker-compose.ci.yml` com `--wait`, mais 4 `curl` (health, login 401, `/metrics`, `/storage` 403). Só no push para `main`, publica 6 imagens no GHCR (a da API, `auth-service`, `log-service`, `prometheus`, `grafana`, `garage`) com as tags `sha-<7>` e `latest`.
- **Portainer:** a stack vem do repositório Git (`docker-compose.yml`) e **puxa as imagens do GHCR**. Não faz build no servidor. Os segredos são variáveis da stack.
- **Domínio:** `marcio-mazega-isw055.lapps.studio`, atrás do proxy HTTPS (Cloudflare) da infra do professor, que encaminha para a porta `${PORT}` do host.
- O banco não está na stack; é fornecido pela infra.

## 9. Frontend

Angular 21, componentes standalone com `loadComponent` (lazy) em `app.routes.ts`, build `npx ng build --configuration production` dentro do `Dockerfile` raiz. O resultado é copiado para `backend/static` e servido pelo FastAPI.

- Páginas: `landing` (`/` e `/planos`), `login`, `reset-password`, `catalogo`, `favoritos`, `comentarios`, `perfil` e `perfil/:id`, `usuarios` (admin), `premium/sucesso`, `premium/cancelado`.
- Componentes: cartão e modal do item do catálogo, `navbar`, `premium-cta`.
- Infra do front: `auth.guard`, `permission.guard`, a diretiva `has-permission` e o `auth.interceptor`. Ainda não tem interceptor de erro nem cliente gerado do OpenAPI.

## 10. Ocorrências de termos do domínio antigo

Na Fase 0, a busca pelos termos do domínio antigo (`scripts/checar_dominio_antigo.sh`) encontrou **689 ocorrências em 77 arquivos**. As maiores concentrações estavam no material da P1 (fonte e PDF da prova), na documentação do sistema anterior, nas telas e serviços do catálogo no front, na integração com a API externa no back e nos testes. Também havia arquivos com nome temático (assets, painel do Grafana, componentes do front) e nomes temáticos na rede e nas imagens do compose.

Na Fase 1, tudo isso saiu: o código foi removido ou renomeado, e o material da P1 e a documentação anterior foram apagados (ADR 007). A busca volta vazia e roda no CI e no pre-commit.

## 11. Como o layout real se encaixa na Parte A.2

O roteiro desenha `services/api/app/`; o repositório tem `backend/app/` com o `Dockerfile` na raiz. Proposta: **manter `backend/` como raiz do serviço de API** (evita mexer no `Dockerfile`, no workflow e no `COPY backend/ .` agora) e criar os contextos dentro dele.

```
backend/app/
  shared/{domain,application,infrastructure,api}/   # novo: ids, UoW, settings, Problem Details, request id, health
  obras/{domain,application,infrastructure,api}/     # novo (Fase 4)
  assinaturas/{domain,application,infrastructure,api}/  # novo; o Stripe atual migra para cá na Fase 9
  admin/                                              # novo (Fase 10), só queries
  clients/      → shared/infrastructure/ (auth_client, log_client)
  core/         → shared/infrastructure/ (config, database) e shared/api/ (api_responses, security)
  routes/       → perfis, auth (ponte), logs, observabilidade e storage continuam como "api" de shared/ ou de seus contextos
  models|repositories|schemas/  → somem com o domínio antigo; perfis vira infraestrutura do contexto de conta
  main.py
backend/tests/ (ou tests/) → unit/ e integration/
db/NNN_*.sql   # novo, na raiz, montado na imagem da API
```

- **Serviço no compose:** proposta de renomear `catalogo` para `api` (e a imagem para `ghcr.io/schinor/nivelo-api`), atualizando o `prometheus.yml` e o compose de dev no mesmo commit, **confirmado pela resposta (a)**.
- **Migrações:** o runner `db/NNN_*.sql` roda no boot da API. O auth-service hoje cria as próprias tabelas com `create_all`. Decisão a registrar no ADR da Fase 1: ou o runner da API vira o único dono do DDL (incluindo `empresas`, `convites` e o `ALTER` de `usuarios`), ou cada serviço roda só os seus arquivos. Recomendo **um runner só, na API**, com os arquivos marcados por contexto, e o `create_all` desligado nos dois serviços. Isso é mais simples de provar ao professor (`db/001_dominio.sql`) e evita corrida de DDL no boot.
- **IDs:** `usuarios.id` continua `INT`; o `UsuarioId` do domínio encapsula esse valor. Empresas, obras, diários e o resto nascem em UUID v7 (`CHAR(36)`).

## 12. Pontos de atenção levantados

1. `ACCESS_TOKEN_EXPIRE_MINUTES=1440` e não há refresh token. Baixar para 15 min sem refresh derruba o usuário a cada 15 min; a Fase 3 precisa de refresh token ou de um valor intermediário (ADR 005).
2. O `reset_tokens.token` é guardado em claro. O convite (Fase 3) deve guardar só o hash; vale corrigir o reset junto.
3. O remetente padrão do Mailtrap era o do projeto anterior. É variável da stack (`MAILTRAP_FROM_EMAIL`, `MAILTRAP_FROM_NAME`): precisa ser trocado no Portainer também.
4. A chave da API externa era obrigatória no `Settings`: removê-la da stack antes de publicar o código novo fazia a API não subir. Resolvido na Fase 1 (o código não lê mais a variável).
5. O Free do HANK+ limita favoritos (`LIMITE_FAVORITOS_FREE`). O limite do Nivelo (obras ativas) só entra na Fase 8; entre a Fase 1 e a 8 não há limite.
6. **O cadastro aceita o papel vindo do corpo** (`payload.role`, só `admin` é recusado): qualquer pessoa se cadastrava com o papel de mais privilégio. **Corrigido na Fase 1:** o cadastro público cria sempre `dono` e ignora qualquer papel enviado.
7. O ambiente local tem Python 3.14, e as dependências fixadas (`pydantic-core`, `Pillow`) não compilam nele. Os testes rodam com `uv` em Python 3.12 (ver Comandos no `CLAUDE.md`).

## 13. O que mudou na Fase 1

- Serviço `catalogo` virou `api`; imagens `ghcr.io/schinor/nivelo-*`; rede `nivelo-network`; containers `nivelo-*-schinor`.
- Domínio antigo removido do back, do front, dos testes, das variáveis e do banco (revisão `api_002_remove_catalogo`, exportada em `db/000_remove_catalogo.sql`).
- Papéis `admin`, `dono`, `encarregado` e `cliente`; cadastro público sempre cria `dono`.
- `alembic upgrade head` no boot da API e do auth-service; a API tem tabela de versão própria (`alembic_version_api`).
- Esqueleto hexagonal em `backend/app/` (`shared`, `obras`, `assinaturas`, `admin`), Request ID, Problem Details e `/health/live` e `/health/ready`.
- ruff, mypy, import-linter e pre-commit no CI.
