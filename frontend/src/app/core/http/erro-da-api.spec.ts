import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { mensagemDe, paraErroDaApi } from './erro-da-api';

function resposta(status: number, error: unknown): HttpErrorResponse {
  return new HttpErrorResponse({ status, error });
}

describe('paraErroDaApi', () => {
  it('usa o type estável como código e o detail como mensagem', () => {
    const e = paraErroDaApi(
      resposta(402, {
        type: 'https://nivelo/erros/plano-limite-excedido',
        detail: 'O plano Free permite 1 obra ativa e você já tem 1.',
        limite: 1,
        atual: 1,
      }),
    );
    expect(e.codigo).toBe('plano-limite-excedido');
    expect(e.status).toBe(402);
    expect(e.mensagem).toContain('1 obra ativa');
    expect(e.problema.limite).toBe(1);
  });

  it('422 de validação aponta os campos', () => {
    const e = paraErroDaApi(
      resposta(422, { type: 'https://nivelo/erros/validacao', detail: 'email: inválido', errors: [{ campo: 'email', mensagem: 'inválido' }] }),
    );
    expect(e.mensagem).toBe('Confira os campos destacados.');
    expect(e.campo('email')).toBe('inválido');
    expect(e.campo('nome')).toBeNull();
  });

  it('sem Problem Details, usa a mensagem do status', () => {
    expect(mensagemDe(resposta(0, null))).toContain('Sem conexão');
    expect(paraErroDaApi(resposta(503, 'html')).codigo).toBe('http-503');
    expect(mensagemDe(new Error('x'))).toBe('Algo deu errado. Tente de novo.');
  });

  it('404 de outra empresa e de recurso inexistente são iguais', () => {
    const e = paraErroDaApi(resposta(404, { type: 'https://nivelo/erros/nao-encontrado', detail: 'Diário não encontrado' }));
    expect([e.codigo, e.mensagem]).toEqual(['nao-encontrado', 'Diário não encontrado']);
  });
});
