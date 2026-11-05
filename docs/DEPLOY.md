# Deploy no Portainer

Troca da stack do projeto anterior para o Nivelo, na **mesma stack**, com o **mesmo subdomínio**
(`https://marcio-mazega-isw055.lapps.studio`), sem porta publicada nova e sem container novo.

> **O primeiro deploy é destrutivo.** No boot, o `alembic upgrade head` do auth-service e da API
> apaga as tabelas do catálogo antigo e do RBAC, converte os papéis e recria o `reset_tokens`.
> Sem o dump conferido do passo 0, **não há volta**. Não pule o passo 0.

Cada passo termina com um **Confirme**: só siga para o próximo depois de conferir.

## Checklist

| # | Passo | Feito |
|---|---|---|
| 0 | Backup: dump conferido, guardado fora do repositório; ensaio das migrações na cópia; variáveis atuais salvas | ☐ |
| 1 | Túnel da Cloudflare: conferido para onde aponta (porta `${PORT}` do host) | ☐ |
| 2 | GHCR: CI verde e as 6 imagens `nivelo-*` puxáveis sem login (ou registry no Portainer) | ☐ |
| 3 | Variáveis: removidas as antigas, adicionadas as novas, `SEED` não é `true` | ☐ |
| 4 | Segredos trocados: `SECRET_KEY`, tokens internos, Stripe, Garage, senha do banco | ☐ |
| 5 | Stack apontando para `https://github.com/Schinor/Nivelo`; *Pull and redeploy*; containers `healthy` (print) | ☐ |
| 6 | `docker stats`: limite de 1 GiB em todos; nada acima de ~700 MiB em uso normal | ☐ |
| 7 | Landing abre sem login; `/health/ready` responde 200; admin entra e troca a senha | ☐ |

---

## 0. Backup do banco

O MariaDB (11.8) é compartilhado e fica fora da stack. Rode o dump numa máquina que alcança o
banco. Se ela não tiver o cliente do MariaDB, use a imagem oficial, com `--rm` para não sobrar
container. A senha vai por variável de ambiente, para não ficar no histórico do shell:

```bash
mkdir -p ~/backups/nivelo && cd ~/backups/nivelo        # FORA do repositório
read -rs MYSQL_PWD && export MYSQL_PWD                  # digite a senha do banco e Enter
ARQ="nivelo-pre-deploy-$(date +%Y%m%d-%H%M).sql.gz"

# com o cliente instalado (mariadb-dump ou mysqldump, mesmas opções):
mariadb-dump --single-transaction --routines --triggers --default-character-set=utf8mb4 \
  -h <host> -P <porta> -u <usuario> <banco> | gzip > "$ARQ"

# ou pela imagem oficial:
docker run --rm -e MYSQL_PWD mariadb:11.8 mariadb-dump --single-transaction --routines --triggers \
  --default-character-set=utf8mb4 -h <host> -P <porta> -u <usuario> <banco> | gzip > "$ARQ"
unset MYSQL_PWD
```

**Confirme** (sem isso, não siga):

```bash
ls -lh "$ARQ"                                   # não pode ter poucos bytes
gunzip -t "$ARQ" && echo "gzip íntegro"
zcat "$ARQ" | grep -c 'CREATE TABLE'            # uma por tabela do banco (usuarios, perfis, roles...)
zcat "$ARQ" | tail -1                           # termina com "-- Dump completed on ..."
```

- O dump tem dados pessoais e hashes de senha. **Nunca** entra no repositório nem em issue.
  Guarde uma segunda cópia fora da máquina (pendrive, drive pessoal).
- Restaurar (só no caminho de volta, ver o fim do documento):
  `gunzip -c "$ARQ" | mariadb -h <host> -P <porta> -u <usuario> -p <banco>`

### 0.1 Ensaio das migrações numa cópia

Aplica as migrações do primeiro deploy numa cópia local do dump. É o mesmo `alembic upgrade head`
que roda no boot dos containers, na mesma ordem (auth-service primeiro; a API só sobe depois que o
auth-service fica saudável).

```bash
docker run -d --rm --name nivelo-ensaio -e MARIADB_ROOT_PASSWORD=ensaio -e MARIADB_DATABASE=ensaio \
  -p 127.0.0.1:33062:3306 mariadb:11.8
sleep 15
gunzip -c ~/backups/nivelo/<arquivo>.sql.gz | docker exec -i nivelo-ensaio mariadb -uroot -pensaio ensaio

cd <repositório do Nivelo>
export DATABASE_URL=mysql+pymysql://root:ensaio@127.0.0.1:33062/ensaio SECRET_KEY=ensaio
(cd auth-service && ../.venv/bin/python -m alembic upgrade head)
(cd backend && ../.venv/bin/python -m alembic upgrade head)
docker exec nivelo-ensaio mariadb -uroot -pensaio ensaio -e "
  SELECT version_num FROM alembic_version; SELECT version_num FROM alembic_version_api;
  SELECT COUNT(*) AS usuarios, SUM(admin_plataforma) AS admins FROM usuarios;"
docker stop nivelo-ensaio
```

Esperado: `007_reset_token_hash` e `api_004_outbox_backoff_e_foto_apos_publicacao`, nenhum erro
no caminho, e a mesma quantidade de usuários do dump. Se der erro aqui, **pare** e traga o erro:
ele aconteceria igual em produção.

### 0.2 Copiar as variáveis atuais

No Portainer: **Stacks → (a stack) → Editor**, em *Environment variables* clique em
**Advanced mode** e copie o texto inteiro (`NOME=valor`, uma por linha) para o gerenciador de
senhas ou um arquivo fora do repositório. Anote também a **Repository URL**, o **branch** e o
**Compose path** atuais. É isso que volta a stack ao estado anterior.

## 1. Túnel da Cloudflare

O compose novo muda o nome do serviço (`catalogo` → `api`) e o do container
(`nivelo-api-schinor`). Isso só é seguro se o túnel apontar para a **porta publicada no host**,
não para o nome do container. A Fase 0 concluiu que aponta para a porta; confira antes de trocar:

- Com acesso ao painel: **Zero Trust → Networks → Tunnels → (o túnel) → Public Hostname** do
  `marcio-mazega-isw055.lapps.studio`. O *Service* deve ser `http://localhost:<PORT>` ou
  `http://<ip do host>:<PORT>`, com o mesmo número da variável `PORT` da stack.
- Sem acesso ao painel (túnel da infra do professor): no host, compare a resposta pública com a
  da porta local:

  ```bash
  URL=https://marcio-mazega-isw055.lapps.studio
  grep '^PORT=' <variáveis salvas no 0.2>          # a porta publicada hoje
  curl -s -o /dev/null -w "público: %{http_code}\n" "$URL/"
  curl -s -o /dev/null -w "local:   %{http_code}\n" "http://localhost:<PORT>/"
  docker ps --format '{{.Names}}\t{{.Ports}}' | grep "<PORT>"   # quem segura a porta hoje
  ```

**Confirme:** o túnel aponta para a porta `PORT`, e a variável `PORT` **não muda** neste deploy.
Se o *Service* for o **nome de um container** (`http://catalogo...:8000`), pare: o túnel quebraria
com o nome novo, e é preciso pedir à infra que troque para a porta antes de seguir.

## 2. Imagens no GHCR

O Portainer não faz build: ele puxa `ghcr.io/schinor/nivelo-{api,auth-service,log-service,prometheus,grafana,garage}`,
que o workflow `ci-cd.yml` publica a cada push na `main` (tags `latest` e `sha-<7 caracteres>`).

1. `git push` da `main` e espere o workflow **CI/CD** ficar verde (testes, stack de CI e publicação).
2. Anote o `sha-<commit>` publicado (`git rev-parse --short=7 HEAD`). Use essa tag no
   `IMAGE_TAG` em vez de `latest`: o deploy fica reprodutível, e voltar uma versão é trocar a tag.
3. Confira que as seis imagens saem **sem login** (é assim que o Portainer vai puxar):

   ```bash
   TAG=sha-$(git rev-parse --short=7 HEAD)
   docker logout ghcr.io
   for n in api auth-service log-service prometheus grafana garage; do
     docker manifest inspect ghcr.io/schinor/nivelo-$n:$TAG >/dev/null && echo "ok  $n" || echo "FALHA $n"
   done
   ```

Se alguma der `FALHA` (`unauthorized`), escolha um dos dois:

- **Pacote público** (recomendado): github.com/Schinor → **Packages → nivelo-<nome> → Package
  settings → Change visibility → Public**. Repita para cada pacote que falhou.
- **Registry no Portainer**: crie um token clássico no GitHub só com `read:packages`; no Portainer,
  **Registries → Add registry → Custom**, URL `ghcr.io`, usuário `Schinor`, senha = o token. Na
  stack, o *Pull and redeploy* passa a usar esse registry.

**Confirme:** as seis linhas `ok`.

## 3. Variáveis da stack

A lista completa do que o compose lê está no `.env.example` (só os nomes). Edite no
**Advanced mode** da stack, a partir do texto salvo no 0.2, **sem aplicar ainda** (o deploy é no
passo 5). Diferença em relação à stack de hoje:

**Remover**
- As **duas variáveis da API externa do catálogo antigo** (a chave e a URL base; o código não as lê
  desde a Fase 1).
- `ACCESS_TOKEN_EXPIRE_MINUTES` (o padrão do compose já é 120, ADR 005).
- O limite de favoritos do plano antigo (`LIMITE_FAVORITOS_FREE`), se existir.

**Adicionar**

| Variável | Valor |
|---|---|
| `APP_ENV` | `production` (com ela, o seed se recusa a rodar e o boot falha se `SEED=true`) |
| `SEED` | `false` (ou ausente). **Nunca** `true` |
| `ADMIN_EMAIL` | seu e-mail (se já tiver conta, ela só vira admin; a senha não muda) |
| `ADMIN_SENHA_INICIAL` | a do passo 4 (mínimo de 12 caracteres) |
| `APP_BASE_URL` | `https://marcio-mazega-isw055.lapps.studio` (link do convite) |
| `STRIPE_PRICE_PRO`, `STRIPE_PRICE_CONSTRUTORA` | vazias até a Fase 9 |
| `AUTH_INTERNAL_TOKEN` | se ainda não existir na stack (valor no passo 4) |
| `IMAGE_TAG` | o `sha-<commit>` do passo 2 |

**Mudar**
- `MAILTRAP_FROM_EMAIL` e `MAILTRAP_FROM_NAME`: remetente do Nivelo (no Mailtrap de produção, o
  e-mail precisa ser do domínio verificado).

**Conferir que continuam iguais:** `PORT` (é para ela que o túnel aponta, passo 1),
`CATALOGO_URL` e `FRONTEND_URL` (a URL `https://` pública), `STORAGE_BUCKET`,
`MAILTRAP_HOST/PORT/USERNAME`, `EMAIL_LOG_LINK_WITHOUT_SMTP=false`.

**Confirme:** `grep -E '^(SEED|APP_ENV)=' ` no texto editado mostra `SEED=false` (ou nada) e
`APP_ENV=production`; as duas variáveis do catálogo antigo e `ACCESS_TOKEN_EXPIRE_MINUTES` sumiram.

## 4. Trocar os segredos

Os segredos da stack existem desde o projeto anterior. O histórico do Git está limpo (nenhum
valor real foi commitado), mas o produto muda e eles trocam junto. Os valores novos vão direto
para o texto do passo 3 e para o gerenciador de senhas, nunca para arquivo no repositório.

### 4.1 Gerados na sua máquina

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "LOG_INTERNAL_TOKEN=$(openssl rand -hex 32)"
echo "AUTH_INTERNAL_TOKEN=$(openssl rand -hex 32)"
echo "PROMETHEUS_PROXY_PASSWORD=$(openssl rand -hex 16)"
echo "GARAGE_RPC_SECRET=$(openssl rand -hex 32)"
echo "ADMIN_SENHA_INICIAL=$(openssl rand -base64 18)"
```

| Segredo | Efeito |
|---|---|
| `SECRET_KEY` | Todo token emitido antes deixa de valer: todos entram de novo. Esperado. |
| `LOG_INTERNAL_TOKEN`, `AUTH_INTERNAL_TOKEN` | Internos entre os serviços; trocam juntos no mesmo deploy. |
| `PROMETHEUS_PROXY_PASSWORD` | Senha do `/prometheus` (usuário `admin`). |
| `GARAGE_RPC_SECRET` | Só o RPC interno do Garage (nó único); vale no próximo boot. |
| `GRAFANA_ADMIN_PASSWORD` | Opcional. O Grafana só lê na **criação** do volume `grafana-data`; com o volume existente, troque pela tela do Grafana ou com `grafana cli admin reset-admin-password <nova>` no console do container. |

### 4.2 Stripe (modo de teste)

No painel do Stripe, **em modo de teste**:

1. **Developers → API keys → Secret key → Roll key**, expiração **agora**. O valor novo vai para
   `STRIPE_SECRET_KEY`.
2. **Developers → Webhooks → (o endpoint `https://marcio-mazega-isw055.lapps.studio/webhooks/stripe`)
   → Signing secret → Roll secret**, expiração **agora**. O valor novo vai para
   `STRIPE_WEBHOOK_SECRET`.

A URL do webhook e o `STRIPE_PRICE_ID` não mudam. Entre o *roll* e o passo 5, o checkout antigo
fica sem Stripe; ninguém paga de verdade em modo de teste.

### 4.3 Garage (chave S3)

O Garage guarda as chaves no volume `garage-meta`; trocar só a variável não basta, a chave nova
precisa existir no Garage e ter acesso ao bucket. A imagem do Garage não tem shell, então o
console do Portainer não abre: rode o binário com `docker exec` no host.

```bash
# na sua máquina: gere o par novo (o Garage exige "GK" + 24 hex e 64 hex)
echo "STORAGE_ACCESS_KEY=GK$(openssl rand -hex 12)"
echo "STORAGE_SECRET_KEY=$(openssl rand -hex 32)"

# no host:
g() { docker exec garage-schinor /garage "$@"; }      # funciona em bash e zsh
g key list                                            # anote o ID da chave antiga
g key import --yes -n nivelo <STORAGE_ACCESS_KEY> <STORAGE_SECRET_KEY>
g bucket allow --read --write --owner <STORAGE_BUCKET> --key <STORAGE_ACCESS_KEY>
g bucket info <STORAGE_BUCKET>                        # as duas chaves aparecem com RWO
```

A chave antiga continua valendo até o passo 5 (o site antigo segue funcionando). **Apague a
antiga só depois** do passo 7: `docker exec garage-schinor /garage key delete --yes <ID antigo>`.

### 4.4 Senha do banco

O `DATABASE_URL` é `mysql+pymysql://<usuario>:<senha>@<host>:<porta>/<banco>`. A troca é feita
**dentro do passo 5**, com os containers antigos já parados (senão eles perdem a conexão no meio).
Deixe pronto agora:

```bash
openssl rand -hex 24          # senha nova: só hex, para não precisar de escape na URL
```

e o `DATABASE_URL` novo, com essa senha, no texto do passo 3. Se o seu usuário do banco **não**
tiver permissão de `ALTER USER` (banco da infra do professor), peça a troca à infra e combine o
momento do passo 5.

**Confirme:** todos os valores novos estão no texto do passo 3 e no gerenciador de senhas; o
Stripe mostra as chaves novas; `garage bucket info` lista a chave nova com acesso.

## 5. Trocar o repositório da stack, pull e redeploy

O compose novo mudou dois nomes, e isso trava o redeploy se nada for feito:

- O serviço da API passou de `catalogo` para `api`. O container antigo da API vira órfão e
  continua segurando a porta `${PORT}`: o `api` novo não sobe ("port is already allocated").
- A rede ganhou o nome `nivelo-network`, **com a mesma sub-rede `10.20.30.0/28`** da rede antiga.
  Enquanto a antiga existir, a nova não é criada ("Pool overlaps with other one").

O site fica fora do ar daqui até o fim do passo 5 (poucos minutos).

1. **Containers**: marque os sete containers da stack (API antiga, `auth-service-schinor`,
   `log-service-schinor`, `garage-schinor`, Redis, Prometheus e Grafana da stack) → **Stop** →
   **Remove**. **Não** marque "remove volumes": `redis-data`, `grafana-data`, `garage-meta` e
   `garage-data` têm os mesmos nomes no compose novo e são reaproveitados.
2. **Networks**: a rede antiga da stack (sub-rede `10.20.30.0/28`) deve ficar sem containers →
   **Remove**.
3. **Senha do banco** (4.4), agora que nada está conectado:

   ```bash
   mariadb -h <host> -P <porta> -u <usuario> -p -e "ALTER USER CURRENT_USER() IDENTIFIED BY '<senha nova>';"
   mariadb -h <host> -P <porta> -u <usuario> -p<senha nova> -e "SELECT 1"     # entra com a nova
   ```

4. **Stacks → (a stack) → Editor/Git**. **Repository URL**: `https://github.com/Schinor/Nivelo`.
   Branch `refs/heads/main`, compose path `docker-compose.yml` (o mesmo de antes).
5. **Environment variables**: cole o texto dos passos 3 e 4 no *Advanced mode*.
6. **Pull and redeploy**, com **Re-pull image** ligado. Se aparecer *Prune services*, ligue.

O primeiro boot demora mais: o auth-service roda as migrações (ensaiadas no 0.1) e só então fica
saudável; a API espera por ele, migra a parte dela e sobe.

**Confirme:** em **Containers**, os sete da stack (`nivelo-api-schinor`, `auth-service-schinor`,
`log-service-schinor`, `garage-schinor`, Redis, Prometheus e Grafana) estão `running` e
`healthy`. **Tire o print** (vai para a Fase 7).

Se algum ficar `unhealthy` ou reiniciando: **Logs** do container. Os mais prováveis são a
variável obrigatória que faltou (`DATABASE_URL`, `SECRET_KEY`), a senha do banco que não bate com
o `DATABASE_URL` (`Access denied`), o erro de migração (compare com o ensaio), a chave do Garage
sem acesso ao bucket (4.3) e a senha do admin com menos de 12 caracteres.

## 6. Memória (`docker stats`)

Pelo terminal do host: `docker stats --no-stream`. Pelo Portainer: **Containers → (container) →
Stats**. A coluna de limite precisa mostrar **1GiB** em todos (o `mem_limit: 1g` do compose), e
o uso normal deve ficar abaixo de ~700 MiB. Referência medida na stack local depois do roteiro
`e2e/`: API ~185 MiB, auth ~110 MiB, log ~50 MiB, Garage ~30 MiB, Redis ~10 MiB, Prometheus
~55 MiB. O Grafana chega a ~470 MiB no boot; acompanhe ele de novo depois de alguns minutos.

**Confirme:** `1GiB` de limite em todos, nenhum acima de ~700 MiB.

## 7. Landing e `/health/ready` em produção

```bash
URL=https://marcio-mazega-isw055.lapps.studio
curl -s -o /dev/null -w "landing: %{http_code}\n" "$URL/"
curl -s -w "\nready: %{http_code}\n" "$URL/health/ready"
curl -s -o /dev/null -w "docs: %{http_code}\n" "$URL/api/docs"
```

Esperado: landing 200, `/health/ready` 200, e no navegador anônimo a landing do Nivelo sem
login. Se o túnel responder 502/1033, o `api` não está ouvindo na `${PORT}`: confira o 5.1
(container antigo segurando a porta) e os logs do `api`.

Depois, o **admin**: entre com o `ADMIN_EMAIL` e a `ADMIN_SENHA_INICIAL`, troque a senha pela
tela da conta e **apague o valor de `ADMIN_SENHA_INICIAL`** da stack (sem as duas variáveis, o
boot não faz nada com o admin). Por fim, apague a chave antiga do Garage (4.3).

**Confirme:** landing e `/health/ready` com 200; admin entrou com a senha nova.

### Depois do deploy: roteiro `e2e/` contra produção

Ver `e2e/README.md`, seção *Em produção*. O roteiro cria contas e uma obra de verdade; use
e-mails seus (`voce+dono@...`, `voce+cliente@...`) para o convite chegar numa caixa que você lê.

---

## Caminho de volta

Se o deploy não estabilizar e não houver correção rápida:

1. **Containers**: Stop e Remove dos containers novos (sem remover os volumes); **Networks**:
   remova a `nivelo-network`.
2. **Banco**: se a senha foi trocada no 5.3, volte a antiga
   (`ALTER USER CURRENT_USER() IDENTIFIED BY '<senha antiga>'`). Depois, apague as tabelas que só o
   Nivelo criou e restaure o dump (ele recria as antigas, com `DROP TABLE IF EXISTS` antes de cada
   uma):

   ```bash
   mariadb -h <host> -P <porta> -u <usuario> -p <banco> -e "SET FOREIGN_KEY_CHECKS=0;
     DROP TABLE IF EXISTS empresas, vinculos, convites, obras, obra_membros, diarios, ocorrencias,
       diario_fotos, diario_revisoes, assinaturas, stripe_eventos, outbox, alembic_version_api;
     SET FOREIGN_KEY_CHECKS=1;"
   gunzip -c ~/backups/nivelo/<arquivo>.sql.gz | mariadb -h <host> -P <porta> -u <usuario> -p <banco>
   ```

3. **Stack**: volte a Repository URL, o branch e o compose path anotados no 0.2, cole de volta as
   variáveis salvas e faça *Pull and redeploy*. Os segredos do Stripe já foram girados: use os
   novos do 4.2 no lugar dos antigos. A chave antiga do Garage só vale se ainda não foi apagada.
4. Confira o subdomínio e os containers `healthy`.

Para voltar só uma versão do Nivelo (sem desfazer a troca de stack), basta mudar o `IMAGE_TAG` para
o `sha-` anterior e fazer o redeploy. As migrações não descem sozinhas; se a versão anterior tiver
esquema diferente, restaure o dump do dia.
