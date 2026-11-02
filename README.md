# Nivelo

**Diário de obra no celular para pequenos empreiteiros: registre o dia em 2 minutos e mostre ao cliente, com foto e data, tudo o que foi feito.**

> Projeto da disciplina ISW055 — professor [github.com/siriani](https://github.com/siriani).
> Continuação do HANK+ (catálogo de filmes), feito com espelhamento do repositório e todo o histórico de commits.

---

## 1. A dor

**Quem sofre:** o empreiteiro ou a pequena construtora com 2 a 10 obras residenciais ao mesmo tempo (reformas, casas, ampliações), sem engenheiro dedicado nem software de gestão.

**Quando:** no fim de cada etapa e, principalmente, no fim da obra, na hora de receber. É nesse momento que o cliente questiona o atraso ("ficou 3 semanas parado"), o material ("comprei 40 sacos de cimento, cadê?") ou o serviço ("isso não estava no combinado").

**Quanto custa hoje:**

- **Dinheiro:** a última parcela (10% a 20% do contrato) fica retida por semanas enquanto se discute. Numa reforma de R$ 60 mil, são R$ 6 mil a R$ 12 mil parados ou perdidos num desconto "pra encerrar a briga".
- **Tempo:** 3 a 5 horas por semana mandando foto no WhatsApp, explicando por áudio e procurando o print de dois meses atrás.
- **Risco:** sem registro de chuva, falta de material ou mudança pedida pelo cliente, o atraso vira culpa do empreiteiro, e o próximo cliente chega pela indicação de alguém insatisfeito.

**Como resolve hoje:** fotos soltas no WhatsApp, caderno no canteiro, planilha que ninguém atualiza ou simplesmente memória.

## 2. Persona

**Valdir Rocha, 47 anos, empreiteiro em Marília/SP.**

- Toca 4 obras ao mesmo tempo com 7 funcionários; dois deles são encarregados que ficam no canteiro.
- Passa o dia entre as obras de caminhonete, resolve tudo pelo celular e não abre computador.
- **O que tenta fazer:** entregar no prazo, receber a última parcela sem discussão e ganhar o próximo cliente por indicação.
- **O que atrapalha:** o cliente liga perguntando "como está a obra?" duas vezes por dia; quando dá atraso por chuva ou por falta do material que o próprio cliente ia comprar, ele não tem como provar. Na última obra, deu R$ 4 mil de desconto para não brigar.
- **Frase dele:** "Eu tenho foto de tudo, o problema é achar."

## 3. Concorrentes e alternativas

| Alternativa | O que faz | O que faz mal para o Valdir |
|---|---|---|
| **Grupo de WhatsApp com o cliente** | Fotos e áudios na hora, de graça | Nada organizado por dia; some no histórico; não tem valor de prova nem relatório |
| **Caderno ou planilha** | Registro do dia no papel ou no Excel | Ninguém atualiza; o cliente não vê; não tem foto; perde-se ou molha |
| **Apps de diário de obra (ex.: Diário de Obra Online, Apruma)** | RDO completo com fotos, clima, efetivo, relatório em PDF | Feitos para engenheiro e construtora média: muitos campos, linguagem técnica, preço pensado para empresa maior |
| **ERPs de construção (ex.: Sienge)** | Gestão completa: orçamento, compras, financeiro | Caros, implantação longa, absurdamente grandes para 4 obras |

## 4. Proposta de valor

**Para o empreiteiro que vive no celular, o Nivelo transforma as fotos que ele já tira em um diário de obra com data, clima e registro imutável, que o cliente acompanha por um link, sem planilha e sem curso.**

## 5. Modelo de receita com Stripe

Cobrança por **empresa** (o dono paga; encarregados e clientes não pagam), assinatura mensal no Stripe.

| Plano | Preço | O que inclui | Limite |
|---|---|---|---|
| **Free** | R$ 0,00 | 1 obra ativa, diário com fotos, 1 encarregado, link do cliente | **1 obra ativa** e **até 3 diários por mês** |
| **Pro** | R$ 59,00/mês | Obras e diários ilimitados, até 5 encarregados, relatório RDO em PDF, resumo semanal por e-mail ao cliente | Sem limite de obras e diários |
| **Team** (futuro) | R$ 149,00/mês | Tudo do Pro, encarregados ilimitados, marca da empresa no relatório | — |

**Por que alguém paga o Pro:** o Free deixa o Valdir provar o valor numa obra. Assim que ele tem a segunda obra, ou o primeiro cliente pergunta "dá pra me mandar o relatório?", ele precisa do Pro. R$ 59 é menos de 1% da parcela que fica retida numa única discussão.

## 6. Métricas de sucesso

| Métrica | O que mostra | Meta inicial (3 meses) |
|---|---|---|
| Empresas cadastradas | Interesse | 50 |
| Ativação: empresas com 5+ diários na 1ª semana | O fluxo central funciona | 40% dos cadastros |
| Assinantes Pro | Disposição de pagar | 10 |
| **MRR** (receita recorrente mensal) | Saúde do negócio | R$ 590 |
| Conversão Free → Pro | O limite do Free está bem calibrado | 15% |
| Retenção mensal (churn) | O produto vira hábito | churn < 8% ao mês |
| Clientes finais que abrem o link | Valor percebido e canal de indicação | 70% das obras ativas |

## 7. Lean Canvas

| Bloco | Nivelo |
|---|---|
| **Problema** | 1) Empreiteiro não consegue provar o que fez, quando e por que atrasou. 2) Cliente sem visibilidade liga o tempo todo. 3) Registro espalhado no WhatsApp e no papel. *Hoje:* WhatsApp, caderno, planilha. |
| **Segmentos de clientes** | Empreiteiros e pequenas construtoras com 2 a 10 obras residenciais. *Primeiros adotantes:* empreiteiros da região de Marília/Tupã/Pompeia que já mandam foto da obra para o cliente pelo WhatsApp. |
| **Proposta única de valor** | Seu diário de obra em 2 minutos pelo celular, com prova que o cliente acompanha por um link. |
| **Solução** | 1) Diário do dia com fotos, clima automático e ocorrências. 2) Histórico imutável (quem registrou, quando, o que mudou). 3) Link do cliente e relatório RDO em PDF. |
| **Canais** | Indicação no próprio link do cliente ("feito com Nivelo"), lojas de material de construção da região, grupos de empreiteiros no WhatsApp/Facebook, Instagram com vídeos curtos de canteiro. |
| **Fontes de receita** | Assinatura mensal por empresa no Stripe: Free R$ 0, Pro R$ 59, Team R$ 149 (futuro). |
| **Estrutura de custos** | VM Proxmox já existente (energia/link), domínio, armazenamento das fotos (Garage), e-mail transacional (Brevo), taxas do Stripe por cobrança, tempo de desenvolvimento e suporte. |
| **Métricas-chave** | Cadastros, ativação (diários na 1ª semana), assinantes Pro, MRR, churn, % de links do cliente abertos. |
| **Vantagem injusta** | Produto feito para quem não é engenheiro (simplicidade como decisão, não falta de recurso); contato direto com empreiteiros da região; o histórico de obras acumulado na conta, que fica caro de abandonar. |

## 8. Mapa de reaproveitamento

| Peça do HANK+ | O que vira no Nivelo |
|---|---|
| Catálogo de filmes (TMDB) | Serviço `obras`: obras, diários do dia, fotos, ocorrências |
| Favoritos | Obras que o cliente acompanha (vínculo cliente ↔ obra) |
| Comentários | Comentários do cliente em cada diário |
| Microsserviço de login (auth-service, rede interna) | Login, cadastro da empresa, convite de encarregado e de cliente |
| RBAC no banco e nas APIs | Papéis `admin` (plataforma), `dono`, `encarregado`, `cliente`; os papéis temáticos de filmes saem |
| Multi-tenancy (novo) | Toda consulta filtra por `empresa_id`, vindo do token, nunca da requisição |
| Esqueci minha senha + e-mail (Mailtrap/Brevo) | Mantido, mais convites, aviso de diário novo e resumo semanal ao cliente |
| Rate limiting por rota | Mantido; mais rígido no upload de fotos e no link público do cliente |
| Logs e auditoria (Redis Streams) | Eventos de negócio: "obra criada", "diário registrado", "diário editado", "foto enviada", "cliente visualizou", "assinatura alterada"; é o próprio valor de prova do produto |
| Upload e perfil (Garage) | Fotos do diário, logo da empresa, foto de perfil |
| Plano Premium (Stripe) | Assinatura Free/Pro por empresa, com checkout, webhooks e portal do cliente |
| Swagger / OpenAPI | API de obras e diários documentada |
| CI/CD (GitHub Actions → GHCR) | Mantido: build e deploy a cada push |
| Observabilidade (Prometheus/Grafana) | Mantida, mais métricas de negócio: diários por dia, assinantes, MRR |
| Portainer, MariaDB, Redis, Garage, subdomínio | Mesma stack e mesmo subdomínio; a troca para este repositório é a Atividade 10 |

## 9. Backlog

As próximas entregas estão nas [issues](../../issues) deste repositório.