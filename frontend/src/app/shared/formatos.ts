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

export const STATUS_DA_OBRA: Record<string, string> = { ativa: 'Em andamento', pausada: 'Pausada', concluida: 'Concluída' };
export const STATUS_DO_DIARIO: Record<string, string> = { rascunho: 'Rascunho', publicado: 'Publicado' };
export const CONDICAO: Partial<Record<string, string>> = { praticavel: 'Praticável', impraticavel: 'Impraticável' };
export const TEMPO: Record<string, string> = {
  ensolarado: 'Ensolarado', nublado: 'Nublado', chuvoso: 'Chuvoso', tempestade: 'Tempestade',
};
export const TEMPO_ICONE: Record<string, string> = { ensolarado: '☀️', nublado: '☁️', chuvoso: '🌧️', tempestade: '⛈️' };
export const TIPO_OCORRENCIA: Partial<Record<string, string>> = {
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

/** "Alves Construções" → "AC"; "josé" → "JO". Para o selo da empresa e o avatar. */
export function iniciais(nome: string | null | undefined): string {
  const partes = (nome ?? '').trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

const fmtDiaDaSemana = new Intl.DateTimeFormat('pt-BR', { weekday: 'short' });
const fmtMesAno = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' });
const fmtHora = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' });
const fmtDiaMes = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' });
const fmtHojeLongo = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' });

/** "2026-11-04" → "QUA" (linha do tempo). */
export function diaDaSemana(iso: string): string {
  return fmtDiaDaSemana.format(dataLocal(iso)).replace('.', '').toUpperCase();
}

/** "2026-11-04" → "04". */
export function diaDoMes(iso: string): string {
  return iso.slice(8, 10);
}

/** "2026-11-04" → "NOVEMBRO 2026" (separador da linha do tempo). */
export function mesAno(iso: string): string {
  return fmtMesAno.format(dataLocal(iso)).replace(' de ', ' ').toUpperCase();
}

/** "2026-11-04" → "04/11". */
export function diaMes(iso: string | null | undefined): string {
  return iso ? fmtDiaMes.format(dataLocal(iso)) : '';
}

/** Instante UTC → "17:42" no fuso de quem usa. */
export function hora(iso: string | null | undefined): string {
  return iso ? fmtHora.format(instante(iso)) : '';
}

/** Hoje por extenso, para o sobretítulo: "QUARTA-FEIRA, 04 DE NOVEMBRO". */
export function hojePorExtenso(agora: Date = new Date()): string {
  return fmtHojeLongo.format(agora).toUpperCase();
}

/** Atividades guardadas como texto, uma por linha (o formulário monta a lista). */
export function linhas(texto: string | null | undefined): string[] {
  return (texto ?? '').split('\n').map((l) => l.replace(/^\s*[-•✓]\s*/, '').trim()).filter(Boolean);
}
