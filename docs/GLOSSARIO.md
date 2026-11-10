# Glossário — linguagem ubíqua do Nivelo

Os nomes abaixo valem para a conversa, o código do domínio, a API e as telas. No código do domínio usamos o termo em português, como está na coluna "No código". Termos técnicos (`repository`, `handler`, `router`) podem ficar em inglês.

| Termo | No código | Significado |
|---|---|---|
| **Empresa** (tenant) | `Empresa`, `EmpresaId` | A conta contratante: quem assina o plano e é dona dos dados. Pode ser pessoa jurídica (construtora, CNPJ) ou física (empreiteiro, engenheiro ou arquiteto autônomo, CPF). Todo dado de domínio pertence a uma empresa. |
| **Usuário** | `UsuarioId` | Uma pessoa com login (e-mail e senha). É global: a mesma pessoa pode ter vínculo com mais de uma empresa. |
| **Vínculo** | `Vinculo` | A ligação entre um usuário e uma empresa, com um papel. É onde mora o papel de negócio. |
| **Empresa ativa** | `TenantContext.empresa_id` | A empresa em nome da qual o usuário está agindo agora. Vem do token, nunca do corpo da requisição. |
| **Dono** | papel `dono` | Quem contrata o Nivelo. Cria obras, convida a equipe e o cliente, e gerencia a assinatura. |
| **Encarregado** | papel `encarregado` | Quem fica no canteiro e registra o diário das obras em que é membro. Também chamado de mestre de obras. |
| **Cliente** | papel `cliente` | O dono do imóvel, que contratou a obra. Acompanha os diários publicados das obras em que é membro. Não paga e não conta no limite do plano. |
| **Admin** | `admin_plataforma` | Quem opera a plataforma Nivelo. Não pertence a nenhuma empresa e não lê dados de obras. |
| **Obra** | `Obra`, `ObraId` | Um serviço de construção ou reforma num endereço, com cliente, período previsto e status (`ativa`, `pausada`, `concluida`). |
| **Membro da obra** | `MembroDaObra` | Um usuário ligado a uma obra específica, como `encarregado` ou `cliente`. |
| **Diário de Obra** (RDO) | `DiarioDeObra`, `DiarioId` | O Relatório Diário de Obra: o registro de um dia de uma obra. Há no máximo um por obra por dia. |
| **Clima** | `Clima(manha, tarde)` | As condições do tempo de manhã e à tarde, registradas no diário. |
| **Condição de trabalho** | `CondicaoDeTrabalho` | Se o dia foi `praticavel` (deu para trabalhar) ou `impraticavel` (chuva forte, falta de material e afins). |
| **Atividades** | `atividades` | O que foi feito no dia, em texto. É obrigatório para publicar. |
| **Efetivo** | `efetivo` | Quantas pessoas trabalharam na obra naquele dia. |
| **Ocorrência** | `Ocorrencia`, `TipoOcorrencia` | Um fato que afeta a obra, com tipo (`chuva`, `falta de material`, `pedido do cliente`, `acidente`, `outro`), descrição e impacto no prazo em dias. |
| **Foto do diário** | `FotoDoDiario`, `ObjectKey` | Uma imagem anexada ao diário, guardada no object storage. O banco guarda só a chave do objeto. |
| **Rascunho** | status `rascunho` | Diário ainda em edição. O cliente não vê. |
| **Publicar** | `DiarioPublicado` | Tornar o diário visível ao cliente. A partir daí ele vale como registro e não é sobrescrito. |
| **Revisão** | `RevisaoDoDiario` | A alteração de um diário já publicado. Exige um motivo e guarda o retrato anterior, para que o histórico de prova continue íntegro. |
| **Comentário** | `Comentario` | Uma mensagem num diário publicado, de qualquer membro da obra. |
| **Plano** | `Plano` | O nível da assinatura da empresa: `free`, `pro` ou `construtora`. |
| **Direitos** | `Direitos` | O que o plano permite: obras ativas, fotos por obra e tamanho da equipe. |
| **Política de plano** | `PoliticaDePlano` | A regra que compara os direitos com o uso atual e recusa a ação que passaria do limite (`LimiteDoPlanoExcedido`). |
| **Assinatura ativa** | `assinaturas_ativas` | Assinatura de plano pago com status `active`. |
| **MRR** | `mrr_centavos` | Receita recorrente mensal: a soma do valor mensal das assinaturas ativas. Hoje é de teste, porque o Stripe está em modo de teste. |
| **Inadimplente** | `inadimplentes` | Empresa de plano pago com pagamento pendente (`past_due` ou `unpaid`). Fica com os direitos do Free. |
| **Evento de domínio** | `EventoDeDominio` | Algo que aconteceu no negócio, nomeado como `recurso.acao` no particípio (ex.: `diario.publicado`). Vai para a auditoria pela outbox. |
