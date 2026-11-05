import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MarcaComponent } from '../../shared/marca.component';

/**
 * Moldura das telas de acesso (entrar, criar conta, senha, convite): painel escuro com a
 * proposta à esquerda no computador; no celular, só a marca no topo e o formulário.
 */
@Component({
  selector: 'app-tela-de-acesso',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MarcaComponent],
  template: `
    <div class="tela">
      <aside class="painel">
        <a routerLink="/" class="marca" aria-label="Nivelo, página inicial"><app-marca [escuro]="true" /></a>
        <div class="proposta">
          <p class="frase">{{ frase() }}</p>
          @if (itens().length) {
            <ul>
              @for (i of itens(); track i) { <li>{{ i }}</li> }
            </ul>
          }
        </div>
        <span class="direitos">© {{ ano }} Nivelo</span>
      </aside>
      <main class="lado-formulario">
        <div class="caixa" [style.max-width.px]="largura()">
          <ng-content />
        </div>
      </main>
    </div>
  `,
  styles: `
    :host { display: block; font-size: 16px; }
    .tela { min-height: 100vh; display: flex; flex-direction: column; }
    .painel { background: var(--escuro); color: var(--escuro-tinta); padding: 14px 20px; display: flex; align-items: center; }
    .marca { text-decoration: none; display: inline-flex; min-height: 44px; align-items: center; }
    .proposta, .direitos { display: none; }
    .lado-formulario { flex: 1; display: flex; justify-content: center; padding: 32px 20px 48px; }
    .caixa { width: 100%; display: flex; flex-direction: column; gap: 18px; }
    @media (min-width: 900px) {
      .tela { flex-direction: row; }
      .painel { flex: 0 1 44%; max-width: 560px; padding: 48px; flex-direction: column; align-items: flex-start; justify-content: space-between; gap: 48px; }
      .proposta { display: flex; flex-direction: column; gap: 20px; max-width: 440px; }
      .frase { font-family: var(--fonte-titulo); font-weight: 700; font-size: 32px; line-height: 1.15; letter-spacing: -0.02em; }
      ul { list-style: none; display: flex; flex-direction: column; gap: 12px; color: var(--escuro-tinta-3); }
      li { display: flex; gap: 10px; }
      li::before { content: '✓'; color: var(--menta); font-weight: 700; }
      .direitos { display: block; font-size: 14px; color: var(--escuro-tinta-2); }
      .lado-formulario { align-items: center; padding: 48px 24px; }
    }
  `,
})
export class TelaDeAcessoComponent {
  readonly frase = input('Cada dia de obra registrado. Cada cliente por dentro.');
  readonly itens = input<string[]>([]);
  readonly largura = input(440);
  readonly ano = new Date().getFullYear();
}
