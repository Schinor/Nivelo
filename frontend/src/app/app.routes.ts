import { Routes } from '@angular/router';
import { adminGuard, authGuard, guestGuard } from './guards/auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/landing/landing.component').then(m => m.LandingComponent),
  },
  {
    path: 'planos',
    loadComponent: () => import('./pages/landing/landing.component').then(m => m.LandingComponent),
  },
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent),
  },
  {
    path: 'reset-password',
    loadComponent: () => import('./pages/reset-password/reset-password.component').then(m => m.ResetPasswordComponent),
  },
  {
    path: 'obras',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/obras/obras.component').then(m => m.ObrasComponent),
  },
  {
    path: 'perfil',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/perfil/perfil.component').then(m => m.PerfilComponent),
  },
  {
    path: 'perfil/:id',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/perfil/perfil.component').then(m => m.PerfilComponent),
  },
  {
    path: 'usuarios',
    canActivate: [adminGuard],
    loadComponent: () => import('./pages/usuarios/usuarios.component').then(m => m.UsuariosComponent),
  },
  {
    path: 'premium/sucesso',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/premium/premium-sucesso.component').then(m => m.PremiumSucessoComponent),
  },
  {
    path: 'premium/cancelado',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/premium/premium-cancelado.component').then(m => m.PremiumCanceladoComponent),
  },
  { path: '**', redirectTo: '' },
];
