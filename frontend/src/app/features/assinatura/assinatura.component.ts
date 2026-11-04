import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { PLANOS } from './planos';

/** Os planos e o caminho para assinar. O checkout do Stripe para o Pro e o Construtora entra
 * na Fase 9; o modal "Limite do plano" (402) traz a pessoa para cá. */
@Component({
  selector: 'app-assinatura',
  imports: [RouterLink],
  template: `
    <main class="pagina pagina-larga">
      <h1>Planos</h1>
      <p class="sub">A cobrança é por empresa: encarregados e clientes não pagam.</p>
      <div class="grade">
        @for (p of planos; track p.codigo) {
          <article class="cartao plano" [class.destaque]="p.destaque">
            <h2>{{ p.nome }}</h2>
            <strong class="preco">{{ p.preco }}</strong>
            <ul>@for (i of p.itens; track i) { <li>{{ i }}</li> }</ul>
            @if (p.codigo !== 'free') {
              @if (auth.ehDono()) {
                <button class="btn btn-bloco" [class.btn-primario]="p.destaque" disabled>Assinatura online em breve</button>
              } @else if (!auth.isLoggedIn()) {
                <a class="btn btn-bloco" routerLink="/login" [queryParams]="{ cadastro: '' }">Começar no Free</a>
              }
            }
          </article>
        }
      </div>
      @if (auth.isLoggedIn() && !auth.ehDono()) {
        <p class="alerta alerta-info">Quem assina é o dono da empresa.</p>
      } @else if (auth.ehDono()) {
        <p class="alerta alerta-info">Enquanto a assinatura online não chega, conclua ou pause uma obra para liberar a vaga do Free.</p>
      }
    </main>
  `,
  styles: `
    .sub { color: var(--ink-muted); margin: 6px 0 var(--space-6); }
    .grade { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); margin-bottom: var(--space-6); }
    .plano { display: grid; gap: var(--space-3); align-content: start; }
    .plano + .plano { margin-top: 0; }
    .plano h2 { margin: 0; }
    .plano.destaque { border-color: var(--gold); }
    .preco { font-size: 1.5rem; color: var(--gold); }
    .plano ul { list-style: none; display: grid; gap: 6px; color: var(--ink-muted); }
    .plano li::before { content: '✓ '; color: var(--gold); }
  `,
})
export class AssinaturaComponent {
  auth = inject(AuthService);
  readonly planos = PLANOS;
}
