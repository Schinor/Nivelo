import { describe, expect, it } from 'vitest';
import { data, dataHora, diaDaSemana, diaDoMes, hoje, iniciais, linhas, plural } from './formatos';

describe('formatos', () => {
  it('hoje vem no fuso do aparelho, no formato da API', () => {
    expect(hoje(new Date(2026, 10, 4, 23, 50))).toBe('2026-11-04');
    expect(hoje(new Date(2026, 0, 9, 0, 5))).toBe('2026-01-09');
  });

  it('data sem hora não volta um dia', () => {
    expect(data('2026-11-04')).toBe('04/11/2026');
  });

  it('instante sem fuso é tratado como UTC', () => {
    expect(dataHora('2026-11-04T18:00:00')).toBe(dataHora('2026-11-04T18:00:00Z'));
    expect(dataHora(null)).toBe('');
  });

  it('plural', () => {
    expect(plural(1, 'pessoa', 'pessoas')).toBe('1 pessoa');
    expect(plural(3, 'pessoa', 'pessoas')).toBe('3 pessoas');
  });

  it('iniciais da empresa e da pessoa', () => {
    expect(iniciais('Alves Construções')).toBe('AC');
    expect(iniciais('José Carlos da Silva')).toBe('JS');
    expect(iniciais('marcos')).toBe('MA');
    expect(iniciais('')).toBe('?');
  });

  it('linha do tempo: dia da semana e do mês sem voltar um dia', () => {
    expect(diaDaSemana('2026-11-04')).toBe('QUA');
    expect(diaDoMes('2026-11-04')).toBe('04');
  });

  it('atividades: uma por linha, sem marcador nem linha vazia', () => {
    expect(linhas('- Laje\n\n• Eletrodutos  \n✓ Cura')).toEqual(['Laje', 'Eletrodutos', 'Cura']);
    expect(linhas(null)).toEqual([]);
  });
});
