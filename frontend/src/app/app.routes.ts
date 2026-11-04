import { Routes } from '@angular/router';
import { adminGuard, authGuard, empresaGuard, guestGuard, papelGuard } from './core/guards/auth.guard';

/** Lazy loading por rota; os guards são só conforto (a API confere papel e empresa). */
export const routes: Routes = [
  { path: '', loadComponent: () => import('./features/landing/landing/landing.component').then((m) => m.LandingComponent) },
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/conta/login/login.component').then((m) => m.LoginComponent),
  },
  { path: 'cadastro', redirectTo: 'login?cadastro=', pathMatch: 'full' },
  {
    path: 'reset-password',
    loadComponent: () =>
      import('./features/conta/reset-password/reset-password.component').then((m) => m.ResetPasswordComponent),
  },
  { path: 'convite', loadComponent: () => import('./features/conta/convite.component').then((m) => m.ConviteComponent) },
  { path: 'obras', canActivate: [authGuard], loadChildren: () => import('./features/obras/obras.routes').then((m) => m.OBRAS_ROUTES) },
  {
    path: 'diarios',
    canActivate: [empresaGuard],
    loadChildren: () => import('./features/diarios/diarios.routes').then((m) => m.DIARIOS_ROUTES),
  },
  {
    path: 'equipe',
    canActivate: [papelGuard('dono')],
    loadComponent: () => import('./features/conta/equipe.component').then((m) => m.EquipeComponent),
  },
  {
    path: 'assinatura',
    loadComponent: () => import('./features/assinatura/assinatura.component').then((m) => m.AssinaturaComponent),
  },
  { path: 'planos', redirectTo: 'assinatura' },
  {
    path: 'perfil',
    canActivate: [authGuard],
    loadComponent: () => import('./features/conta/perfil/perfil.component').then((m) => m.PerfilComponent),
  },
  {
    path: 'perfil/:id',
    canActivate: [authGuard],
    loadComponent: () => import('./features/conta/perfil/perfil.component').then((m) => m.PerfilComponent),
  },
  {
    path: 'usuarios',
    canActivate: [adminGuard],
    loadComponent: () => import('./features/admin/usuarios/usuarios.component').then((m) => m.UsuariosComponent),
  },
  {
    path: 'premium/sucesso',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/assinatura/premium/premium-sucesso.component').then((m) => m.PremiumSucessoComponent),
  },
  {
    path: 'premium/cancelado',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/assinatura/premium/premium-cancelado.component').then((m) => m.PremiumCanceladoComponent),
  },
  { path: '**', redirectTo: '' },
];
