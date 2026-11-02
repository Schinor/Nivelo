import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export function permissionGuard(requiredPermission: string): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);

    if (!auth.isLoggedIn()) {
      router.navigate(['/login']);
      return false;
    }

    if (auth.hasPermission(requiredPermission)) {
      return true;
    }

    // Se logado mas sem permissão específica para a rota, redireciona para as obras
    router.navigate(['/obras']);
    return false;
  };
}
