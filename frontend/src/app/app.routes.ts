import { Routes } from '@angular/router';
import { adminGuard, authGuard, empresaGuard, guestGuard, papelGuard } from './core/guards/auth.guard';

/**
 * Lazy loading por rota; os guards são só conforto (a API confere papel e empresa).
 * As telas públicas ficam fora da casca; as logadas, dentro dela (barra lateral / navegação inferior).
 */
export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () => import('./features/landing/landing/landing.component').then((m) => m.LandingComponent),
  },
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/conta/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'cadastro',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/conta/cadastro.component').then((m) => m.CadastroComponent),
  },
  {
    path: 'recuperar-senha',
    loadComponent: () => import('./features/conta/recuperar-senha.component').then((m) => m.RecuperarSenhaComponent),
  },
  {
    path: 'reset-password',
    loadComponent: () =>
      import('./features/conta/reset-password/reset-password.component').then((m) => m.ResetPasswordComponent),
  },
  { path: 'convite', loadComponent: () => import('./features/conta/convite.component').then((m) => m.ConviteComponent) },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./core/layout/casca.component').then((m) => m.CascaComponent),
    children: [
      { path: 'obras', loadChildren: () => import('./features/obras/obras.routes').then((m) => m.OBRAS_ROUTES) },
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
      {
        path: 'conta',
        loadComponent: () => import('./features/conta/perfil/perfil.component').then((m) => m.PerfilComponent),
      },
      { path: 'perfil', redirectTo: 'conta', pathMatch: 'full' },
      {
        path: 'empresas/nova',
        loadComponent: () => import('./features/conta/criar-empresa.component').then((m) => m.CriarEmpresaComponent),
      },
      {
        path: 'admin',
        canActivate: [adminGuard],
        loadComponent: () => import('./features/admin/painel/painel.component').then((m) => m.PainelComponent),
      },
      {
        path: 'usuarios',
        canActivate: [adminGuard],
        loadComponent: () => import('./features/admin/usuarios/usuarios.component').then((m) => m.UsuariosComponent),
      },
    ],
  },
  { path: 'planos', redirectTo: '/', pathMatch: 'full' },
  { path: '**', redirectTo: '' },
];
