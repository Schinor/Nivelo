-- Gerado por scripts/exportar_sql.sh a partir do Alembic. Não edite à mão.
-- Dialeto: MariaDB 10.7+ (tipo UUID nativo). Ordem de aplicação: db/README.md.

-- ===== api: api_003_dominio:api_004_outbox_e_fotos =====
-- Running upgrade api_003_dominio -> api_004_outbox_e_fotos

ALTER TABLE outbox ADD COLUMN proxima_tentativa_em DATETIME;

ALTER TABLE outbox ADD COLUMN ultimo_erro VARCHAR(500);

ALTER TABLE diario_fotos ADD COLUMN apos_publicacao BOOL NOT NULL DEFAULT false;

UPDATE alembic_version_api SET version_num='api_004_outbox_e_fotos' WHERE alembic_version_api.version_num = 'api_003_dominio';

