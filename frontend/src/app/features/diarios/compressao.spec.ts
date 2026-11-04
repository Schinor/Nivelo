import { describe, expect, it } from 'vitest';
import { dimensoes, LADO_MAXIMO } from './compressao';

describe('dimensoes da foto comprimida', () => {
  it('reduz o lado maior para 1600 px mantendo a proporção', () => {
    expect(dimensoes(4000, 3000)).toEqual({ largura: LADO_MAXIMO, altura: 1200 });
    expect(dimensoes(3000, 4000)).toEqual({ largura: 1200, altura: LADO_MAXIMO });
  });

  it('não amplia foto pequena', () => {
    expect(dimensoes(800, 600)).toEqual({ largura: 800, altura: 600 });
  });
});
