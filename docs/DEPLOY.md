# Deploy no Portainer

Troca da stack do projeto anterior para o Nivelo, na **mesma stack**, com o **mesmo subdomínio**
(`https://marcio-mazega-isw055.lapps.studio`), sem porta publicada nova e sem container novo.

> **O primeiro deploy é destrutivo.** No boot, o `alembic upgrade head` do auth-service e da API
> apaga as tabelas do catálogo antigo e do RBAC, converte os papéis e recria o `reset_tokens`.
> Sem o dump conferido do passo 1, **não há volta**. Não pule o passo 1.

## Checklist

| # | Passo | Feito |
|---|---|---|
| 1 | Backup: dump do banco conferido e guardado fora do repositório | ☐ |
| 2 | Ensaio: migrações rodadas numa cópia local do dump, sem erro | ☐ |
| 3 | Variáveis atuais da stack copiadas para um lugar seguro (caminho de volta) | ☐ |
| 4 | GHCR: `main` publicado, CI verde e as 6 imagens `nivelo-*` com a tag `sha-<commit>` | ☐ |
| 5 | Segredos novos gerados | ☐ |
| 6 | Variáveis: removidas as antigas, adicionadas as novas, trocados os segredos | ☐ |
| 7 | Containers antigos e a rede antiga removidos (volumes preservados) | ☐ |
| 8 | Stack apontando para `https://github.com/Schinor/Nivelo`; *Pull and redeploy* | ☐ |
| 9 | Containers `running` e `healthy` (print) | ☐ |
| 10 | Túnel da Cloudflare: subdomínio abre a landing; `/health/ready` responde 200 | ☐ |
| 11 | `docker stats`: limite de 1 GiB em todos; nada acima de ~700 MiB em uso normal | ☐ |
| 12 | Admin entra; senha inicial trocada | ☐ |

---

## 1. Backup do banco

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

**Conferir** (sem isso, não siga):

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

## 2. Ensaio das migrações numa cópia

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

## 3. Copiar as variáveis atuais

No Portainer: **Stacks → (a stack) → Editor**, em *Environment variables* clique em
**Advanced mode** e copie o texto inteiro (`NOME=valor`, uma por linha) para o gerenciador de
senhas ou um arquivo fora do repositório. Anote também a **Repository URL**, o **branch** e o
**Compose path** atuais. É isso que volta a stack ao estado anterior.

## 4. Imagens no GHCR

O Portainer não faz build: ele puxa `ghcr.io/schinor/nivelo-{api,auth-service,log-service,prometheus,grafana,garage}`,
que o workflow `ci-cd.yml` publica a cada push na `main` (tags `latest` e `sha-<7 caracteres>`).
Os seis pacotes já são públicos, então não é preciso cadastrar o registry no Portainer.

1. `git push` da `main` e espere o workflow **CI/CD** ficar verde (testes, stack de CI e publicação).
2. Anote o `sha-<commit>` publicado (`git rev-parse --short=7 HEAD`). Use essa tag no
   `IMAGE_TAG` em vez de `latest`: o deploy fica reprodutível, e voltar uma versão é trocar a tag.

## 5. Segredos novos

Os segredos da stack existem desde o projeto anterior. O histórico do Git está limpo (nenhum
valor real foi commitado), mas o produto muda e eles trocam junto. Gere na sua máquina:

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "LOG_INTERNAL_TOKEN=$(openssl rand -hex 32)"
echo "AUTH_INTERNAL_TOKEN=$(openssl rand -hex 32)"
echo "PROMETHEUS_PROXY_PASSWORD=$(openssl rand -hex 16)"
echo "ADMIN_SENHA_INICIAL=$(openssl rand -base64 18)"
```

| Segredo | Troca? | Efeito |
|---|---|---|
| `SECRET_KEY` | **Sim** | Todo token emitido antes deixa de valer: todos entram de novo. Esperado. |
| `LOG_INTERNAL_TOKEN`, `AUTH_INTERNAL_TOKEN` | **Sim** | Internos entre os serviços; trocam juntos no mesmo deploy. |
| `PROMETHEUS_PROXY_PASSWORD` | **Sim** | Senha do `/prometheus` (usuário `admin`). |
| `GRAFANA_ADMIN_PASSWORD` | Opcional | O Grafana só lê na **criação** do volume `grafana-data`. Com o volume existente, troque pela tela do Grafana (perfil do admin) ou pelo console do container: `grafana cli admin reset-admin-password <nova>`. |
| `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `GARAGE_RPC_SECRET` | **Não agora** | O Garage cria a chave a partir dessas variáveis; trocar exige migrar a permissão do bucket. Fica para depois da entrega. |
| `DATABASE_URL` | Não | Fornecida pela infra. |
| `STRIPE_*`, `MAILTRAP_*` | Não | Modo de teste; o Stripe é revisto na Fase 9. |

## 6. Variáveis da stack

A lista completa do que o compose lê está no `.env.example` (só os nomes). Diferença em
relação à stack de hoje:

**Remover**
- As **duas variáveis da API externa do catálogo antigo** (a chave e a URL base; o código não as lê
  desde a Fase 1).
- O limite de favoritos do plano antigo (`LIMITE_FAVORITOS_FREE`).

**Mudar**
- `ACCESS_TOKEN_EXPIRE_MINUTES`: de `1440` para `120` (ADR 005), ou apague a linha (o padrão é 120).
- `MAILTRAP_FROM_EMAIL` e `MAILTRAP_FROM_NAME`: remetente do Nivelo (no Mailtrap de produção, o
  e-mail precisa ser do domínio verificado).
- `SECRET_KEY`, `LOG_INTERNAL_TOKEN`, `AUTH_INTERNAL_TOKEN`, `PROMETHEUS_PROXY_PASSWORD`: os valores do passo 5.
- `IMAGE_TAG`: `sha-<commit>` do passo 4.

**Adicionar**

| Variável | Valor |
|---|---|
| `APP_ENV` | `production` (com ela, o seed se recusa a rodar) |
| `SEED` | `false` |
| `APP_BASE_URL` | `https://marcio-mazega-isw055.lapps.studio` (link do convite) |
| `ADMIN_EMAIL` | seu e-mail (se já tiver conta, ela só vira admin; a senha não muda) |
| `ADMIN_SENHA_INICIAL` | a do passo 5 (mínimo de 12 caracteres) |
| `STRIPE_PRICE_PRO`, `STRIPE_PRICE_CONSTRUTORA` | vazias até a Fase 9 |
| `AUTH_INTERNAL_TOKEN` | se ainda não existir na stack |

**Conferir que continuam iguais:** `PORT` (é para ela que o túnel aponta), `DATABASE_URL`,
`CATALOGO_URL` e `FRONTEND_URL` (a URL `https://` pública), `STORAGE_*`, `GARAGE_RPC_SECRET`,
`MAILTRAP_HOST/PORT/USERNAME/PASSWORD`, `EMAIL_LOG_LINK_WITHOUT_SMTP=false`.

## 7. Containers e rede antigos

O compose novo mudou dois nomes, e isso trava o redeploy se nada for feito:

- O serviço da API passou de `catalogo` para `api`. O container antigo da API vira órfão e
  continua segurando a porta `${PORT}`: o `api` novo não sobe ("port is already allocated").
- A rede ganhou o nome `nivelo-network`, **com a mesma sub-rede `10.20.30.0/28`** da rede antiga.
  Enquanto a antiga existir, a nova não é criada ("Pool overlaps with other one").

O site fica fora do ar deste passo até o 9 (poucos minutos):

1. **Containers**: marque os sete containers da stack (API antiga, `auth-service-schinor`,
   `log-service-schinor`, `garage-schinor`, Redis, Prometheus e Grafana da stack) → **Stop** →
   **Remove**. **Não** marque "remove volumes": `redis-data`, `grafana-data`, `garage-meta` e
   `garage-data` têm os mesmos nomes no compose novo e são reaproveitados.
2. **Networks**: a rede antiga da stack (sub-rede `10.20.30.0/28`) deve ficar sem containers →
   **Remove**.

## 8. Apontar a stack para o Nivelo e subir

1. **Stacks → (a stack) → Editor/Git**.
2. **Repository URL**: `https://github.com/Schinor/Nivelo`. Branch `refs/heads/main`, compose
   path `docker-compose.yml` (o mesmo de antes).
3. **Environment variables**: aplique o passo 6 (dá para colar no *Advanced mode*).
4. **Pull and redeploy**, com **Re-pull image** ligado. Se aparecer *Prune services*, ligue.

O primeiro boot demora mais: o auth-service roda as migrações (passo 2) e só então fica saudável;
a API espera por ele, migra a parte dela e sobe.

## 9. Containers saudáveis

Em **Containers**, os sete da stack: `nivelo-api-schinor`, `auth-service-schinor`,
`log-service-schinor`, `garage-schinor`, Redis, Prometheus e Grafana, todos `running` e
`healthy`. **Tire o print** (vai para a Fase 7).

Se algum ficar `unhealthy` ou reiniciando: **Logs** do container. Os mais prováveis são a
variável obrigatória que faltou (`DATABASE_URL`, `SECRET_KEY`), o erro de migração (compare com o
ensaio) e a senha do admin com menos de 12 caracteres.

## 10. Túnel da Cloudflare e verificação

O túnel do `lapps.studio` é da infra do professor e aponta para a **porta publicada no host**
(`${PORT}`), não para o nome do container. Nada muda nele, desde que `PORT` continue a mesma.

```bash
URL=https://marcio-mazega-isw055.lapps.studio
curl -s -o /dev/null -w "landing: %{http_code}\n" "$URL/"
curl -s -w "\nready: %{http_code}\n" "$URL/health/ready"
curl -s -o /dev/null -w "docs: %{http_code}\n" "$URL/api/docs"
```

Esperado: landing 200, `/health/ready` 200, e no navegador anônimo a landing do Nivelo sem
login. Se o túnel responder 502/1033, o `api` não está ouvindo na `${PORT}`: confira o passo 7
(container antigo segurando a porta) e os logs do `api`.

## 11. Memória (`docker stats`)

Pelo terminal do host: `docker stats --no-stream`. Pelo Portainer: **Containers → (container) →
Stats**. A coluna de limite precisa mostrar **1GiB** em todos (o `mem_limit: 1g` do compose), e
o uso normal deve ficar abaixo de ~700 MiB. Referência medida na stack local depois do roteiro
`e2e/`: API ~185 MiB, auth ~110 MiB, log ~50 MiB, Garage ~30 MiB, Redis ~10 MiB, Prometheus
~55 MiB. O Grafana chega a ~470 MiB no boot; acompanhe ele de novo depois de alguns minutos.

## 12. Admin

Entre com o `ADMIN_EMAIL` e a `ADMIN_SENHA_INICIAL`, troque a senha pelo perfil e depois
**apague o valor de `ADMIN_SENHA_INICIAL`** da stack (sem as duas variáveis, o boot não faz nada
com o admin).

---

## Caminho de volta

Se o deploy não estabilizar e não houver correção rápida:

1. **Containers**: Stop e Remove dos containers novos (sem remover os volumes); **Networks**:
   remova a `nivelo-network`.
2. **Banco**: apague as tabelas que só o Nivelo criou e restaure o dump (ele recria as antigas,
   com `DROP TABLE IF EXISTS` antes de cada uma):

   ```bash
   mariadb -h <host> -P <porta> -u <usuario> -p <banco> -e "SET FOREIGN_KEY_CHECKS=0;
     DROP TABLE IF EXISTS empresas, vinculos, convites, obras, obra_membros, diarios, ocorrencias,
       diario_fotos, diario_revisoes, assinaturas, stripe_eventos, outbox, alembic_version_api;
     SET FOREIGN_KEY_CHECKS=1;"
   gunzip -c ~/backups/nivelo/<arquivo>.sql.gz | mariadb -h <host> -P <porta> -u <usuario> -p <banco>
   ```

3. **Stack**: volte a Repository URL, o branch e o compose path anotados no passo 3, cole de volta
   as variáveis salvas e faça *Pull and redeploy*.
4. Confira o subdomínio e os containers `healthy`.

Para voltar só uma versão do Nivelo (sem desfazer a troca de stack), basta mudar o `IMAGE_TAG` para
o `sha-` anterior e fazer o redeploy. As migrações não descem sozinhas; se a versão anterior tiver
esquema diferente, restaure o dump do dia.
