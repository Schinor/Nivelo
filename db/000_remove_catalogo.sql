-- Gerado por scripts/exportar_sql.sh a partir do Alembic (api, api_001_perfis:api_002_remove_catalogo). Não edite à mão.
-- Dialeto: MariaDB.
-- Running upgrade api_001_perfis -> api_002_remove_catalogo

DROP TABLE IF EXISTS favoritos;

DROP TABLE IF EXISTS comentarios;

UPDATE alembic_version_api SET version_num='api_002_remove_catalogo' WHERE alembic_version_api.version_num = 'api_001_perfis';

