/** Estilos comuns aos formulários das telas de acesso (título, passo, rodapé com link). */
export const ESTILOS_DE_ACESSO = `
  .passo { font-family: var(--fonte-mono); font-size: 13px; color: var(--tinta-3); }
  .titulo { display: flex; flex-direction: column; gap: 6px; }
  h1 { font-weight: 800; font-size: 30px; }
  @media (min-width: 720px) { h1 { font-size: 34px; } }
  .titulo p { color: var(--tinta-2); }
  .rodape-form { text-align: center; color: var(--tinta-3); font-size: 15px; }
  .rodape-form a { font-weight: 600; }
  .linha-rotulo { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .linha-rotulo a { font-size: 14px; font-weight: 500; }
`;
