import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../auth.service';

const SEM_REDIRECIONAR = ['/api/auth/login', '/api/auth/cadastro', '/api/convites/aceitar'];

/**
 * Põe o token nas chamadas à API. Não vai para /storage: lá a autorização é a própria
 * assinatura da URL. Um 401 fora do login limpa a sessão e volta para o login.
 */
export const tokenInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = auth.token();
  const paraApi = req.url.startsWith('/api/') || req.url.startsWith('api/');
  const comToken = token && paraApi ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(comToken).pipe(
    catchError((e: unknown) => {
      if (e instanceof HttpErrorResponse && e.status === 401 && !SEM_REDIRECIONAR.some((u) => req.url.includes(u))) {
        auth.limparSessao();
        router.navigate(['/login'], { queryParams: { voltar: router.url } });
      }
      return throwError(() => e);
    }),
  );
};
