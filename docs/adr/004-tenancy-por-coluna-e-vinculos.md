# ADR 004 — Tenancy por coluna, com usuário global e vínculos

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

O Nivelo é multi-tenant: cada empresa só pode ver os próprios dados. O banco é um MariaDB compartilhado, fornecido pela infraestrutura, então não dá para criar um banco ou um esquema por cliente. Além disso, a mesma pessoa pode trabalhar para mais de uma empresa (um engenheiro encarregado em duas construtoras) ou acompanhar obras de mais de um empreiteiro (um cliente com duas reformas).

## Decisão

- **Isolamento por coluna:** toda tabela de domínio tem `empresa_id`, num banco só. Os índices compostos começam por `empresa_id`.
- **O tenant é a conta contratante:** `empresas` com `tipo_pessoa` (PF/PJ) e `documento` opcional. Um autônomo é uma empresa PF de uma pessoa só.
- **Usuário global, papel por vínculo (opção B):** `usuarios` não tem `empresa_id` nem papel de negócio. A tabela `vinculos(usuario_id, empresa_id, papel, ativo)` diz em que empresas a pessoa está e com qual papel.
- **Empresa ativa no token:** o JWT carrega `empresa_id` e `papel` do vínculo ativo. `POST /auth/empresa-ativa` troca a empresa e emite um token novo.
- **O `empresa_id` vem só do token**, nunca do corpo, da query ou da URL. Registro de outra empresa responde **404**, sem revelar que existe.
- **Três camadas de proteção:** a `TenantContext` montada do JWT; repositórios que recebem o `empresa_id` no construtor (não existe `get(id)` sem tenant); e uma rede de segurança no ORM (`with_loader_criteria` a partir de um `ContextVar`) que faz uma consulta sem tenant definido **falhar**. As exceções (painel admin, webhook do Stripe, relay da outbox) usam uma sessão marcada `sem_tenant=True`.
- IDs públicos em UUID v7, nunca autoincremento.

## Consequências

- Um esquecimento no repositório é pego pela rede de segurança, e cada recurso tem teste de integração com duas empresas (B pedindo o recurso de A recebe 404).
- O login de quem tem vários vínculos escolhe o mais recente; a tela de troca de empresa fica para depois de 13/11 (o endpoint já nasce pronto).
- Uma troca de papel só vale no próximo token (ver ADR 005).
- Os dados de todas as empresas dividem as mesmas tabelas: um bug grave de consulta é mais perigoso do que com banco separado. Por isso a rede de segurança falha fechada.
