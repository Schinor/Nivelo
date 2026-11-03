-- Gerado por scripts/exportar_sql.sh a partir do Alembic. Não edite à mão.
-- Dialeto: MariaDB 10.7+ (tipo UUID nativo). Ordem de aplicação: db/README.md.

-- ===== auth: base:004_premium_stripe =====
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 001_auth_service

CREATE TABLE usuarios (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    nome VARCHAR(100) NOT NULL, 
    email VARCHAR(150) NOT NULL, 
    senha_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(20) NOT NULL DEFAULT 'usuario', 
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE reset_tokens (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    token VARCHAR(128) NOT NULL, 
    usuario_id INTEGER NOT NULL, 
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP, 
    expira_em DATETIME NOT NULL, 
    usado BOOL NOT NULL DEFAULT 0, 
    PRIMARY KEY (id), 
    FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_reset_tokens_token ON reset_tokens (token);

INSERT INTO alembic_version (version_num) VALUES ('001_auth_service');

-- Running upgrade 001_auth_service -> 002_rbac_system

CREATE TABLE permissions (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    action VARCHAR(50) NOT NULL, 
    resource VARCHAR(50) NOT NULL, 
    description VARCHAR(255), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_permission_action_resource UNIQUE (action, resource)
);

CREATE TABLE roles (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    slug VARCHAR(50) NOT NULL, 
    description VARCHAR(255), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_roles_slug ON roles (slug);

CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL, 
    permission_id INTEGER NOT NULL, 
    PRIMARY KEY (role_id, permission_id), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
    FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

ALTER TABLE usuarios ADD COLUMN role_id INTEGER;

ALTER TABLE usuarios ADD FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE SET NULL;

UPDATE alembic_version SET version_num='002_rbac_system' WHERE alembic_version.version_num = '001_auth_service';

-- Running upgrade 002_rbac_system -> 003_user_permissions

CREATE TABLE user_permissions (
    usuario_id INTEGER NOT NULL, 
    permission_id INTEGER NOT NULL, 
    concedida BOOL NOT NULL DEFAULT true, 
    PRIMARY KEY (usuario_id, permission_id), 
    FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
    FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

UPDATE alembic_version SET version_num='003_user_permissions' WHERE alembic_version.version_num = '002_rbac_system';

-- Running upgrade 003_user_permissions -> 004_premium_stripe

ALTER TABLE usuarios ADD COLUMN premium BOOL NOT NULL DEFAULT false;

ALTER TABLE usuarios ADD COLUMN stripe_customer_id VARCHAR(255);

ALTER TABLE usuarios ADD COLUMN stripe_subscription_id VARCHAR(255);

ALTER TABLE usuarios ADD COLUMN premium_desde DATETIME;

CREATE TABLE stripe_eventos_processados (
    event_id VARCHAR(255) NOT NULL, 
    tipo VARCHAR(100) NOT NULL, 
    processado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (event_id)
);

UPDATE alembic_version SET version_num='004_premium_stripe' WHERE alembic_version.version_num = '003_user_permissions';


-- ===== api: base:api_002_remove_catalogo =====
CREATE TABLE alembic_version_api (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_api_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> api_001_perfis

CREATE TABLE perfis (
    usuario_id INTEGER NOT NULL, 
    bio VARCHAR(280), 
    foto_key VARCHAR(255), 
    foto_bytes INTEGER, 
    atualizado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (usuario_id)
);

INSERT INTO alembic_version_api (version_num) VALUES ('api_001_perfis');

-- Running upgrade api_001_perfis -> api_002_remove_catalogo

DROP TABLE IF EXISTS favoritos;

DROP TABLE IF EXISTS comentarios;

UPDATE alembic_version_api SET version_num='api_002_remove_catalogo' WHERE alembic_version_api.version_num = 'api_001_perfis';

