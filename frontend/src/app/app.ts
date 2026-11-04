import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AvisosComponent } from './core/layout/avisos.component';
import { NavbarComponent } from './core/layout/navbar/navbar.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, NavbarComponent, AvisosComponent],
  template: `
    <app-navbar />
    <router-outlet />
    <app-avisos />
  `,
  styles: [`:host { display: block; }`],
})
export class App {}
