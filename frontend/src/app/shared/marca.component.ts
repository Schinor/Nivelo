import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** A marca: o nível de bolha e "nivelo". `escuro` é para fundo escuro (bolha menta). */
@Component({
  selector: 'app-marca',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="nivel" aria-hidden="true"><i></i></span>
    <span class="nome">nivelo</span>
  `,
  styles: `
    :host { display: inline-flex; align-items: center; gap: 10px; color: var(--tinta); --bolha: var(--verde); }
    :host(.escuro) { color: var(--escuro-tinta); --bolha: var(--menta); }
    .nivel { position: relative; display: inline-block; width: 34px; height: 16px; border: 2px solid currentColor; border-radius: 9px; }
    .nivel i { position: absolute; left: 50%; top: 50%; width: 10px; height: 8px; margin: -4px 0 0 -5px; border-radius: 5px; background: var(--bolha); }
    .nome { font-family: var(--fonte-titulo); font-weight: 800; font-size: 22px; letter-spacing: -0.02em; line-height: 1; }
    :host(.pequena) .nivel { width: 28px; height: 14px; border-radius: 8px; }
    :host(.pequena) .nivel i { width: 8px; height: 6px; margin: -3px 0 0 -4px; border-radius: 3px; }
    :host(.pequena) .nome { font-size: 19px; }
  `,
  host: { '[class.escuro]': 'escuro()', '[class.pequena]': 'pequena()' },
})
export class MarcaComponent {
  readonly escuro = input(false);
  readonly pequena = input(false);
}
