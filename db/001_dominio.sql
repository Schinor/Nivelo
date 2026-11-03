-- Gerado por scripts/exportar_sql.sh a partir do Alembic. Não edite à mão.
-- Dialeto: MariaDB 10.7+ (tipo UUID nativo). Ordem de aplicação: db/README.md.

-- ===== auth: 004_premium_stripe:005_identidade =====
-- Running upgrade 004_premium_stripe -> 005_identidade

CREATE TABLE empresas (
    id UUID NOT NULL, 
    nome VARCHAR(160) NOT NULL, 
    tipo_pessoa ENUM('PF','PJ') NOT NULL, 
    documento VARCHAR(18), 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_empresas_documento UNIQUE (documento)
);

ALTER TABLE usuarios ADD COLUMN admin_plataforma BOOL NOT NULL DEFAULT false;

UPDATE usuarios SET admin_plataforma = TRUE WHERE role = 'admin';

CREATE TABLE vinculos (
    usuario_id INTEGER NOT NULL, 
    empresa_id UUID NOT NULL, 
    papel ENUM('dono','encarregado','cliente') NOT NULL, 
    ativo BOOL NOT NULL DEFAULT true, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (usuario_id, empresa_id), 
    CONSTRAINT fk_vinculos_usuario FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
    CONSTRAINT fk_vinculos_empresa FOREIGN KEY(empresa_id) REFERENCES empresas (id) ON DELETE CASCADE
);

CREATE INDEX ix_vinculos_empresa_papel ON vinculos (empresa_id, papel);

CREATE TABLE convites (
    id UUID NOT NULL, 
    empresa_id UUID NOT NULL, 
    email VARCHAR(150) NOT NULL, 
    papel ENUM('encarregado','cliente') NOT NULL, 
    obra_id UUID, 
    token_hash CHAR(64) NOT NULL, 
    expira_em DATETIME NOT NULL, 
    usado_em DATETIME, 
    criado_por INTEGER NOT NULL, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_convites_token_hash UNIQUE (token_hash), 
    CONSTRAINT fk_convites_empresa FOREIGN KEY(empresa_id) REFERENCES empresas (id) ON DELETE CASCADE, 
    CONSTRAINT fk_convites_criado_por FOREIGN KEY(criado_por) REFERENCES usuarios (id)
);

CREATE INDEX ix_convites_empresa_email ON convites (empresa_id, email);

UPDATE alembic_version SET version_num='005_identidade' WHERE alembic_version.version_num = '004_premium_stripe';


-- ===== api: api_002_remove_catalogo:api_003_dominio =====
-- Running upgrade api_002_remove_catalogo -> api_003_dominio

CREATE TABLE obras (
    id UUID NOT NULL, 
    empresa_id UUID NOT NULL, 
    nome VARCHAR(160) NOT NULL, 
    logradouro VARCHAR(200) NOT NULL, 
    cidade VARCHAR(120) NOT NULL, 
    uf CHAR(2) NOT NULL, 
    latitude NUMERIC(9, 6), 
    longitude NUMERIC(9, 6), 
    cliente_nome VARCHAR(160) NOT NULL, 
    data_inicio DATE NOT NULL, 
    previsao_termino DATE NOT NULL, 
    status ENUM('ativa','pausada','concluida') NOT NULL DEFAULT 'ativa', 
    versao INTEGER NOT NULL DEFAULT '1', 
    removida_em DATETIME, 
    criado_por INTEGER NOT NULL, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    atualizado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_obras_empresa_id UNIQUE (empresa_id, id), 
    CONSTRAINT ck_obras_periodo CHECK (previsao_termino >= data_inicio)
);

CREATE INDEX ix_obras_empresa_status ON obras (empresa_id, status);

CREATE TABLE obra_membros (
    obra_id UUID NOT NULL, 
    usuario_id INTEGER NOT NULL, 
    empresa_id UUID NOT NULL, 
    papel ENUM('encarregado','cliente') NOT NULL, 
    adicionado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (obra_id, usuario_id), 
    CONSTRAINT fk_obra_membros_obra FOREIGN KEY(empresa_id, obra_id) REFERENCES obras (empresa_id, id) ON DELETE CASCADE
);

CREATE INDEX ix_obra_membros_empresa_usuario ON obra_membros (empresa_id, usuario_id);

CREATE TABLE diarios (
    id UUID NOT NULL, 
    empresa_id UUID NOT NULL, 
    obra_id UUID NOT NULL, 
    data DATE NOT NULL, 
    clima_manha VARCHAR(20), 
    clima_tarde VARCHAR(20), 
    condicao ENUM('praticavel','impraticavel') NOT NULL DEFAULT 'praticavel', 
    atividades TEXT, 
    efetivo INTEGER NOT NULL DEFAULT '0', 
    observacoes TEXT, 
    status ENUM('rascunho','publicado') NOT NULL DEFAULT 'rascunho', 
    autor_id INTEGER NOT NULL, 
    versao INTEGER NOT NULL DEFAULT '1', 
    publicado_em DATETIME, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    atualizado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_diarios_obra_data UNIQUE (obra_id, data), 
    CONSTRAINT uq_diarios_empresa_id UNIQUE (empresa_id, id), 
    CONSTRAINT ck_diarios_efetivo CHECK (efetivo >= 0), 
    CONSTRAINT fk_diarios_obra FOREIGN KEY(empresa_id, obra_id) REFERENCES obras (empresa_id, id)
);

CREATE INDEX ix_diarios_empresa_obra_data ON diarios (empresa_id, obra_id, data);

CREATE TABLE ocorrencias (
    id UUID NOT NULL, 
    empresa_id UUID NOT NULL, 
    diario_id UUID NOT NULL, 
    tipo ENUM('chuva','falta_de_material','pedido_do_cliente','acidente','outro') NOT NULL, 
    descricao TEXT NOT NULL, 
    impacto_prazo_dias INTEGER, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT fk_ocorrencias_diario FOREIGN KEY(empresa_id, diario_id) REFERENCES diarios (empresa_id, id) ON DELETE CASCADE
);

CREATE TABLE diario_fotos (
    id UUID NOT NULL, 
    empresa_id UUID NOT NULL, 
    diario_id UUID NOT NULL, 
    object_key VARCHAR(255) NOT NULL, 
    content_type VARCHAR(50) NOT NULL, 
    tamanho_bytes INTEGER NOT NULL, 
    legenda VARCHAR(280), 
    enviado_por INTEGER NOT NULL, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_diario_fotos_object_key UNIQUE (object_key), 
    CONSTRAINT fk_diario_fotos_diario FOREIGN KEY(empresa_id, diario_id) REFERENCES diarios (empresa_id, id) ON DELETE CASCADE
);

CREATE TABLE diario_revisoes (
    id UUID NOT NULL, 
    empresa_id UUID NOT NULL, 
    diario_id UUID NOT NULL, 
    versao_anterior INTEGER NOT NULL, 
    snapshot JSON NOT NULL, 
    motivo VARCHAR(500) NOT NULL, 
    autor_id INTEGER NOT NULL, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT fk_diario_revisoes_diario FOREIGN KEY(empresa_id, diario_id) REFERENCES diarios (empresa_id, id)
);

CREATE TABLE comentarios (
    id UUID NOT NULL, 
    empresa_id UUID NOT NULL, 
    diario_id UUID NOT NULL, 
    autor_id INTEGER NOT NULL, 
    texto TEXT NOT NULL, 
    criado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT fk_comentarios_diario FOREIGN KEY(empresa_id, diario_id) REFERENCES diarios (empresa_id, id)
);

CREATE TABLE assinaturas (
    empresa_id UUID NOT NULL, 
    plano ENUM('free','pro','construtora') NOT NULL DEFAULT 'free', 
    status VARCHAR(32) NOT NULL DEFAULT 'active', 
    stripe_customer_id VARCHAR(255), 
    stripe_subscription_id VARCHAR(255), 
    stripe_price_id VARCHAR(255), 
    valor_mensal_centavos INTEGER NOT NULL DEFAULT '0', 
    periodo_fim DATETIME, 
    cancelar_no_fim BOOL NOT NULL DEFAULT false, 
    atualizado_em DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (empresa_id), 
    CONSTRAINT uq_assinaturas_customer UNIQUE (stripe_customer_id), 
    CONSTRAINT uq_assinaturas_subscription UNIQUE (stripe_subscription_id)
);

CREATE TABLE stripe_eventos (
    event_id VARCHAR(255) NOT NULL, 
    tipo VARCHAR(100) NOT NULL, 
    recebido_em DATETIME NOT NULL DEFAULT now(), 
    processado_em DATETIME, 
    erro TEXT, 
    PRIMARY KEY (event_id)
);

CREATE TABLE outbox (
    id UUID NOT NULL, 
    tipo VARCHAR(100) NOT NULL, 
    payload JSON NOT NULL, 
    ocorrido_em DATETIME NOT NULL, 
    publicado_em DATETIME, 
    tentativas INTEGER NOT NULL DEFAULT '0', 
    PRIMARY KEY (id)
);

CREATE INDEX ix_outbox_pendentes ON outbox (publicado_em, ocorrido_em);

UPDATE alembic_version_api SET version_num='api_003_dominio' WHERE alembic_version_api.version_num = 'api_002_remove_catalogo';

