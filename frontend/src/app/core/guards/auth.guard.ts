import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService, Papel } from '../auth.service';

/**
 * Guards de navegação. São só conforto: quem decide é a API (403 e 404). Eles evitam abrir
 * uma tela cujas ações a pessoa não pode fazer.
 */
export const authGuard: CanActivateFn = (_rota, estado) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isLoggedIn()) return true;
  return router.createUrlTree(['/login'], { queryParams: { voltar: estado.url } });
};

/** Só quem tem empresa ativa no token (o admin e quem ainda não criou empresa vão para /obras). */
export const empresaGuard: CanActivateFn = (_rota, estado) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isLoggedIn()) return router.createUrlTree(['/login'], { queryParams: { voltar: estado.url } });
  return auth.papel() ? true : router.createUrlTree(['/obras']);
};

/** Só os papéis informados, na empresa ativa. */
export function papelGuard(...papeis: Papel[]): CanActivateFn {
  return (_rota, estado) => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (!auth.isLoggedIn()) return router.createUrlTree(['/login'], { queryParams: { voltar: estado.url } });
    const papel = auth.papel();
    return papel && papeis.includes(papel) ? true : router.createUrlTree(['/obras']);
  };
}

export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isLoggedIn()) return router.createUrlTree(['/login']);
  return auth.isAdmin() ? true : router.createUrlTree(['/obras']);
};

export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.isLoggedIn() ? router.createUrlTree(['/obras']) : true;
};
