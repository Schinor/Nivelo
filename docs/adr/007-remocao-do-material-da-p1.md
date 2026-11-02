# ADR 007 — Remoção do material da P1 deste repositório

- **Status:** aceito
- **Data:** 02/11/2026

## Contexto

Este repositório começou como espelho do projeto anterior da disciplina, com todo o histórico de commits. Ele trazia a prova P1 (fonte e PDF), os prints da P1, a documentação do sistema anterior, o guia de estilo e os relatórios de infraestrutura daquela fase. A avaliação do Nivelo procura, no repositório inteiro, qualquer referência ao domínio antigo.

## Decisão

- **Apagar** esse material do repositório, sem mover para uma pasta de histórico.
- O repositório anterior continua sendo a evidência da P1, e o histórico do git deste repositório guarda todos os arquivos.
- A regra vale sem exceções: a busca pelos termos do domínio antigo no repositório inteiro deve voltar vazia. O `scripts/checar_dominio_antigo.sh` faz essa busca, e o CI e o pre-commit o rodam a cada mudança. O padrão no script usa classes de caractere (`h[a]nks`), para que o próprio script não seja encontrado pela busca.

## Consequências

- Quem quiser o material antigo consulta o repositório anterior ou um commit anterior a esta decisão.
- A documentação do Nivelo é escrita do zero, a partir do mapa da Fase 0 (`docs/MAPA_ATUAL.md`), do glossário e destes ADRs.
