-- Gerado por scripts/exportar_sql.sh a partir do Alembic. Não edite à mão.
-- Dialeto: MariaDB 10.7+ (tipo UUID nativo). Ordem de aplicação: db/README.md.

-- ===== auth: 005_identidade:006_contrai_papel_antigo =====
-- Running upgrade 005_identidade -> 006_contrai_papel_antigo

ALTER TABLE usuarios DROP FOREIGN KEY usuarios_ibfk_1;

ALTER TABLE usuarios DROP COLUMN role_id;

ALTER TABLE usuarios DROP COLUMN role;

DROP TABLE user_permissions;

DROP TABLE role_permissions;

DROP TABLE roles;

DROP TABLE permissions;

UPDATE alembic_version SET version_num='006_contrai_papel_antigo' WHERE alembic_version.version_num = '005_identidade';

