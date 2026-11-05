import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AvisosComponent } from './core/layout/avisos.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, AvisosComponent],
  template: `
    <router-outlet />
    <app-avisos />
  `,
  styles: [`:host { display: block; }`],
})
export class App {}
