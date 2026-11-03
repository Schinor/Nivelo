-- Seed de DESENVOLVIMENTO do Nivelo. Escrito à mão; nunca rode em produção.
-- A API aplica este arquivo no boot só com SEED=true, depois das migrações.
-- Idempotente: INSERT IGNORE com IDs fixos e chaves únicas, então rodar de novo não duplica nada.
-- Senha de todos os usuários: nivelo-dev-123 (hash bcrypt abaixo).
--
-- Empresa A (PF): Rocha Reformas, do empreiteiro Valdir. Empresa B (PJ): Construtora Horizonte.
-- Cada uma tem dono, encarregado, cliente, uma obra e a assinatura Free.
-- Diários: dois na obra de A (um publicado com ocorrência e comentário, um rascunho) e um publicado na obra de B.

-- ── Identidade (tabelas do auth-service) ────────────────────────────────────

INSERT IGNORE INTO empresas (id, nome, tipo_pessoa, documento) VALUES
  ('0190f3a0-0000-7000-8000-00000000000a', 'Rocha Reformas', 'PF', NULL),
  ('0190f3a0-0000-7000-8000-00000000000b', 'Construtora Horizonte', 'PJ', NULL);

INSERT IGNORE INTO usuarios (nome, email, senha_hash, role) VALUES
  ('Valdir Rocha', 'dono.a@example.com', '$2b$12$Utzq6LgTN34IB5tX9ygnWeNMqX301LeBob2bXr6atN3ILkzmGjNPm', 'dono'),
  ('José Carlos', 'encarregado.a@example.com', '$2b$12$Utzq6LgTN34IB5tX9ygnWeNMqX301LeBob2bXr6atN3ILkzmGjNPm', 'encarregado'),
  ('Jorge Lima', 'cliente.a@example.com', '$2b$12$Utzq6LgTN34IB5tX9ygnWeNMqX301LeBob2bXr6atN3ILkzmGjNPm', 'cliente'),
  ('Helena Prado', 'dono.b@example.com', '$2b$12$Utzq6LgTN34IB5tX9ygnWeNMqX301LeBob2bXr6atN3ILkzmGjNPm', 'dono'),
  ('Marcos Souza', 'encarregado.b@example.com', '$2b$12$Utzq6LgTN34IB5tX9ygnWeNMqX301LeBob2bXr6atN3ILkzmGjNPm', 'encarregado'),
  ('Lúcia Alves', 'cliente.b@example.com', '$2b$12$Utzq6LgTN34IB5tX9ygnWeNMqX301LeBob2bXr6atN3ILkzmGjNPm', 'cliente');

INSERT IGNORE INTO vinculos (usuario_id, empresa_id, papel)
  SELECT u.id, v.empresa_id, v.papel FROM usuarios u JOIN (
    SELECT 'dono.a@example.com' AS email, '0190f3a0-0000-7000-8000-00000000000a' AS empresa_id, 'dono' AS papel
    UNION ALL SELECT 'encarregado.a@example.com', '0190f3a0-0000-7000-8000-00000000000a', 'encarregado'
    UNION ALL SELECT 'cliente.a@example.com', '0190f3a0-0000-7000-8000-00000000000a', 'cliente'
    UNION ALL SELECT 'dono.b@example.com', '0190f3a0-0000-7000-8000-00000000000b', 'dono'
    UNION ALL SELECT 'encarregado.b@example.com', '0190f3a0-0000-7000-8000-00000000000b', 'encarregado'
    UNION ALL SELECT 'cliente.b@example.com', '0190f3a0-0000-7000-8000-00000000000b', 'cliente'
  ) v ON v.email = u.email;

-- ── Assinaturas (API) ───────────────────────────────────────────────────────

INSERT IGNORE INTO assinaturas (empresa_id) VALUES
  ('0190f3a0-0000-7000-8000-00000000000a'),
  ('0190f3a0-0000-7000-8000-00000000000b');

-- ── Gestão de Obras (API) ───────────────────────────────────────────────────

INSERT IGNORE INTO obras (id, empresa_id, nome, logradouro, cidade, uf, cliente_nome, data_inicio, previsao_termino, criado_por)
  SELECT '0190f3a0-0000-7000-8000-0000000000a1', '0190f3a0-0000-7000-8000-00000000000a',
         'Reforma da casa do Sr. Jorge', 'Rua das Acácias, 120', 'Marília', 'SP', 'Jorge Lima',
         '2026-10-01', '2026-12-20', id
  FROM usuarios WHERE email = 'dono.a@example.com';

INSERT IGNORE INTO obras (id, empresa_id, nome, logradouro, cidade, uf, cliente_nome, data_inicio, previsao_termino, criado_por)
  SELECT '0190f3a0-0000-7000-8000-0000000000b1', '0190f3a0-0000-7000-8000-00000000000b',
         'Ampliação da residência Alves', 'Av. Sampaio Vidal, 900', 'Marília', 'SP', 'Lúcia Alves',
         '2026-09-15', '2027-01-31', id
  FROM usuarios WHERE email = 'dono.b@example.com';

INSERT IGNORE INTO obra_membros (obra_id, usuario_id, empresa_id, papel)
  SELECT m.obra_id, u.id, m.empresa_id, m.papel FROM usuarios u JOIN (
    SELECT 'encarregado.a@example.com' AS email, '0190f3a0-0000-7000-8000-0000000000a1' AS obra_id,
           '0190f3a0-0000-7000-8000-00000000000a' AS empresa_id, 'encarregado' AS papel
    UNION ALL SELECT 'cliente.a@example.com', '0190f3a0-0000-7000-8000-0000000000a1', '0190f3a0-0000-7000-8000-00000000000a', 'cliente'
    UNION ALL SELECT 'encarregado.b@example.com', '0190f3a0-0000-7000-8000-0000000000b1', '0190f3a0-0000-7000-8000-00000000000b', 'encarregado'
    UNION ALL SELECT 'cliente.b@example.com', '0190f3a0-0000-7000-8000-0000000000b1', '0190f3a0-0000-7000-8000-00000000000b', 'cliente'
  ) m ON m.email = u.email;

INSERT IGNORE INTO diarios (id, empresa_id, obra_id, data, clima_manha, clima_tarde, condicao, atividades, efetivo, observacoes, status, autor_id, publicado_em)
  SELECT '0190f3a0-0000-7000-8000-0000000000d1', '0190f3a0-0000-7000-8000-00000000000a', '0190f3a0-0000-7000-8000-0000000000a1',
         '2026-10-30', 'ensolarado', 'chuvoso', 'impraticavel',
         'Demolição da parede da cozinha e retirada do entulho pela manhã. À tarde a chuva parou o serviço.',
         4, 'Caçamba trocada às 10h.', 'publicado', id, '2026-10-30 18:00:00'
  FROM usuarios WHERE email = 'encarregado.a@example.com';

INSERT IGNORE INTO diarios (id, empresa_id, obra_id, data, clima_manha, clima_tarde, condicao, atividades, efetivo, status, autor_id)
  SELECT '0190f3a0-0000-7000-8000-0000000000d2', '0190f3a0-0000-7000-8000-00000000000a', '0190f3a0-0000-7000-8000-0000000000a1',
         '2026-10-31', 'nublado', 'nublado', 'praticavel',
         'Contrapiso da cozinha.', 3, 'rascunho', id
  FROM usuarios WHERE email = 'encarregado.a@example.com';

INSERT IGNORE INTO diarios (id, empresa_id, obra_id, data, clima_manha, clima_tarde, condicao, atividades, efetivo, status, autor_id, publicado_em)
  SELECT '0190f3a0-0000-7000-8000-0000000000d3', '0190f3a0-0000-7000-8000-00000000000b', '0190f3a0-0000-7000-8000-0000000000b1',
         '2026-10-30', 'ensolarado', 'ensolarado', 'praticavel',
         'Concretagem da laje do quarto novo.', 6, 'publicado', id, '2026-10-30 17:30:00'
  FROM usuarios WHERE email = 'encarregado.b@example.com';

INSERT IGNORE INTO ocorrencias (id, empresa_id, diario_id, tipo, descricao, impacto_prazo_dias) VALUES
  ('0190f3a0-0000-7000-8000-0000000000e1', '0190f3a0-0000-7000-8000-00000000000a', '0190f3a0-0000-7000-8000-0000000000d1',
   'chuva', 'Chuva forte a partir das 13h, serviço externo suspenso', 1);

INSERT IGNORE INTO comentarios (id, empresa_id, diario_id, autor_id, texto)
  SELECT '0190f3a0-0000-7000-8000-0000000000c1', '0190f3a0-0000-7000-8000-00000000000a', '0190f3a0-0000-7000-8000-0000000000d1',
         id, 'Obrigado pelas fotos. Pode seguir com o contrapiso quando secar.'
  FROM usuarios WHERE email = 'cliente.a@example.com';
