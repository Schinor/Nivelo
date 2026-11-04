/** Formatos de data e rótulos do negócio, em português, no fuso de quem usa. */

const fmtData = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
const fmtDataLonga = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
const fmtDataHora = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
});

/** "2026-11-04" (data sem hora) → Date ao meio-dia local, para não virar o dia anterior. */
function dataLocal(iso: string): Date {
  const [a, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(a, m - 1, d, 12);
}

/** A API manda instantes em UTC; sem fuso no texto, trata como UTC. */
function instante(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function data(iso: string | null | undefined): string {
  return iso ? fmtData.format(dataLocal(iso)) : '';
}

export function dataLonga(iso: string | null | undefined): string {
  return iso ? fmtDataLonga.format(dataLocal(iso)) : '';
}

export function dataHora(iso: string | null | undefined): string {
  return iso ? fmtDataHora.format(instante(iso)).replace(',', ' às') : '';
}

/** Hoje no fuso do aparelho, no formato da API ("2026-11-04"). */
export function hoje(agora: Date = new Date()): string {
  const m = String(agora.getMonth() + 1).padStart(2, '0');
  const d = String(agora.getDate()).padStart(2, '0');
  return `${agora.getFullYear()}-${m}-${d}`;
}

export const STATUS_DA_OBRA: Record<string, string> = { ativa: 'Ativa', pausada: 'Pausada', concluida: 'Concluída' };
export const STATUS_DO_DIARIO: Record<string, string> = { rascunho: 'Rascunho', publicado: 'Publicado' };
export const CONDICAO: Record<string, string> = { praticavel: 'Dia praticável', impraticavel: 'Dia impraticável' };
export const TEMPO: Record<string, string> = {
  ensolarado: 'Ensolarado', nublado: 'Nublado', chuvoso: 'Chuvoso', tempestade: 'Tempestade',
};
export const TEMPO_ICONE: Record<string, string> = { ensolarado: '☀️', nublado: '☁️', chuvoso: '🌧️', tempestade: '⛈️' };
export const TIPO_OCORRENCIA: Record<string, string> = {
  chuva: 'Chuva',
  falta_de_material: 'Falta de material',
  pedido_do_cliente: 'Pedido do cliente',
  acidente: 'Acidente',
  outro: 'Outro',
};
export const PAPEL: Record<string, string> = { dono: 'Dono', encarregado: 'Encarregado', cliente: 'Cliente' };

export function plural(n: number, um: string, varios: string): string {
  return `${n} ${n === 1 ? um : varios}`;
}
