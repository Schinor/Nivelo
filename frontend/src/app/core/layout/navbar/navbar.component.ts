import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../auth.service';

@Component({
  selector: 'app-navbar',
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.css',
})
export class NavbarComponent {
  auth = inject(AuthService);
  router = inject(Router);

  get roleBadge(): { name: string; class: string } {
    if (this.auth.isAdmin()) {
      return { name: 'Admin', class: 'badge-admin' };
    }
    switch (this.auth.papel()) {
      case 'dono':
        return { name: 'Dono', class: 'badge-dono' };
      case 'encarregado':
        return { name: 'Encarregado', class: 'badge-encarregado' };
      case 'cliente':
        return { name: 'Cliente', class: 'badge-cliente' };
      default:
        return { name: 'Sem papel', class: 'badge-neutro' };
    }
  }

  logout() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
