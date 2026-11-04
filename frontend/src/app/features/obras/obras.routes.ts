import { Routes } from '@angular/router';
import { papelGuard } from '../../core/guards/auth.guard';

/** /obras/... O parâmetro da rota chega como input do componente (`obraId`). */
export const OBRAS_ROUTES: Routes = [
  { path: '', loadComponent: () => import('./lista-de-obras.component').then((m) => m.ListaDeObrasComponent) },
  {
    path: 'nova',
    canActivate: [papelGuard('dono')],
    loadComponent: () => import('./obra-form.component').then((m) => m.ObraFormComponent),
  },
  { path: ':obraId', loadComponent: () => import('./obra-detalhe.component').then((m) => m.ObraDetalheComponent) },
  {
    path: ':obraId/editar',
    canActivate: [papelGuard('dono')],
    loadComponent: () => import('./obra-form.component').then((m) => m.ObraFormComponent),
  },
  {
    path: ':obraId/diarios/novo',
    canActivate: [papelGuard('dono', 'encarregado')],
    loadComponent: () => import('../diarios/diario-form.component').then((m) => m.DiarioFormComponent),
  },
];
