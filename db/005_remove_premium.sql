-- Gerado por scripts/exportar_sql.sh a partir do Alembic. Não edite à mão.
-- Dialeto: MariaDB 10.7+ (tipo UUID nativo). Ordem de aplicação: db/README.md.

-- ===== auth: 007_reset_token_hash:008_remove_premium =====
-- Running upgrade 007_reset_token_hash -> 008_remove_premium

ALTER TABLE usuarios DROP COLUMN premium;

ALTER TABLE usuarios DROP COLUMN stripe_customer_id;

ALTER TABLE usuarios DROP COLUMN stripe_subscription_id;

ALTER TABLE usuarios DROP COLUMN premium_desde;

DROP TABLE stripe_eventos_processados;

UPDATE alembic_version SET version_num='008_remove_premium' WHERE alembic_version.version_num = '007_reset_token_hash';

