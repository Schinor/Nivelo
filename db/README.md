# Esquema do banco em SQL

Os arquivos `0NN_*.sql` são **gerados** a partir das migrações do Alembic por `scripts/exportar_sql.sh` (dialeto MariaDB 10.7+). Não edite à mão: uma mudança no esquema começa por uma revisão do Alembic (ADR 008).

| Arquivo | Conteúdo |
|---|---|
| `000_remove_catalogo.sql` | Esquema herdado do projeto anterior (usuários, papéis, reset de senha, perfis), já sem as tabelas do catálogo antigo |
| `001_dominio.sql` | Identidade do Nivelo (empresas, vínculos, convites) e domínio (obras, diários, ocorrências, fotos, revisões, comentários, assinaturas, eventos do Stripe e outbox) |
| `002_contrai_papel_antigo.sql` | Contração do papel antigo: sai `usuarios.role`/`role_id` e as tabelas de RBAC (ADR 009) |
| `003_reset_token_hash.sql` | `reset_tokens` recriada com `token_hash` (SHA-256), como os convites; invalida os tokens emitidos antes |
| `004_outbox_backoff_e_foto_apos_publicacao.sql` | `outbox.proxima_tentativa_em` e `ultimo_erro` (backoff do relay, ADR 012) e `diario_fotos.apos_publicacao` |
| `005_remove_premium.sql` | Sai o premium por usuário (`usuarios.premium`, `premium_desde`, `stripe_*` e `stripe_eventos_processados`): a assinatura agora é da empresa, na tabela `assinaturas` (ADR 007) |
| `900_seed_dev.sql` | Dados de desenvolvimento: 2 empresas, cada uma com dono, encarregado, cliente e uma obra, e 3 diários. Escrito à mão. **Nunca em produção.** |

## Banco vazio

Em ordem, num banco vazio (os `0NN` criam as tabelas de versão do Alembic, então depois disso `alembic upgrade head` não tem nada a aplicar):

```bash
for f in db/0*.sql; do mariadb -h <host> -u <usuario> -p <banco> < "$f"; done
# ou, sem o cliente do MariaDB:
cd backend && python -m app.shared.infrastructure.scripts_sql "mysql+pymysql://<usuario>:<senha>@<host>/<banco>" ../db/0*.sql
```

Os arquivos são para banco **vazio**. Num banco que já existe (produção), quem atualiza o esquema é o `alembic upgrade head` no boot de cada serviço.

## Seed de desenvolvimento

A API aplica o `900_seed_dev.sql` no boot quando `SEED=true` (depois das migrações). Com `APP_ENV=production`, o seed se recusa a rodar e o container não sobe. O seed é idempotente: rodar de novo não duplica nada. A senha de todos os usuários do seed é `nivelo-dev-123`.

## Conferir tudo

`MARIADB_URL=mysql+pymysql://root:<senha>@127.0.0.1:3306 scripts/verificar_migracoes.sh` sobe o esquema pelo Alembic e pelos `.sql`, compara os dois e aplica o seed duas vezes. O CI roda o mesmo script num MariaDB 11.8.
