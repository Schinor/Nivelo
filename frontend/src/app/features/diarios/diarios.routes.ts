import { Routes } from '@angular/router';
import { papelGuard } from '../../core/guards/auth.guard';

/** /diarios/... A mesma tela serve ao cliente, sem os controles de escrita. */
export const DIARIOS_ROUTES: Routes = [
  { path: ':diarioId', loadComponent: () => import('./diario-detalhe.component').then((m) => m.DiarioDetalheComponent) },
  {
    path: ':diarioId/editar',
    canActivate: [papelGuard('dono', 'encarregado')],
    loadComponent: () => import('./diario-form.component').then((m) => m.DiarioFormComponent),
  },
];
