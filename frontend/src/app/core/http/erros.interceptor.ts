import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AvisosService } from '../avisos.service';
import { paraErroDaApi } from './erro-da-api';

/**
 * Converte todo erro HTTP da API em `ErroDaApi` (Problem Details → mensagem), para as telas
 * mostrarem `erro.mensagem` e decidirem pelo `codigo`.
 *
 * O 402 (limite do plano) abre o modal "Limite do plano" com o botão para /assinatura, em
 * qualquer tela. Sem conexão (status 0) vira um aviso rápido.
 */
export const errosInterceptor: HttpInterceptorFn = (req, next) => {
  const avisos = inject(AvisosService);
  return next(req).pipe(
    catchError((e: unknown) => {
      if (!(e instanceof HttpErrorResponse)) return throwError(() => e);
      const erro = paraErroDaApi(e);
      if (erro.status === 402) {
        avisos.abrirLimiteDoPlano(erro.problema);
      } else if (erro.status === 0) {
        avisos.erro(erro.mensagem);
      }
      return throwError(() => erro);
    }),
  );
};
