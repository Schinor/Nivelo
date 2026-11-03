-- Gerado por scripts/exportar_sql.sh a partir do Alembic. Não edite à mão.
-- Dialeto: MariaDB 10.7+ (tipo UUID nativo). Ordem de aplicação: db/README.md.

-- ===== auth: 006_contrai_papel_antigo:007_reset_token_hash =====
-- Running upgrade 006_contrai_papel_antigo -> 007_reset_token_hash

DROP TABLE reset_tokens;

CREATE TABLE reset_tokens (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    token_hash CHAR(64) NOT NULL, 
    usuario_id INTEGER NOT NULL, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    expira_em DATETIME NOT NULL, 
    usado BOOL NOT NULL DEFAULT false, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_reset_tokens_token_hash UNIQUE (token_hash), 
    CONSTRAINT fk_reset_tokens_usuario FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);

CREATE INDEX ix_reset_tokens_usuario_criado ON reset_tokens (usuario_id, criado_em);

UPDATE alembic_version SET version_num='007_reset_token_hash' WHERE alembic_version.version_num = '006_contrai_papel_antigo';

