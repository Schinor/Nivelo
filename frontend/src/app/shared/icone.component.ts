import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Traços dos ícones do design (24×24, contorno). Decorativos: sempre com aria-hidden. */
const ICONES = {
  obras: ['M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6'],
  equipe: ['M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2', 'M23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8'],
  assinatura: ['M1 10h22'],
  conta: ['M4 21a8 8 0 0 1 16 0'],
  sair: ['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9'],
  mais: ['M12 5v14M5 12h14'],
  voltar: ['m15 18-6-6 6-6'],
  alerta: ['M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z', 'M12 9v4M12 17h.01'],
  camera: ['M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z'],
  cadeado: ['M7 11V7a5 5 0 0 1 10 0v4'],
  escudo: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z', 'm9 12 2 2 4-4'],
  link: ['M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7', 'M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7'],
  documento: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', 'M14 2v6h6M8 13h8M8 17h5'],
  limite: ['M3 21h18M5 21V8l7-5 7 5v13', 'M12 10v4M12 17h.01'],
  info: ['M12 8v4M12 16h.01'],
  trocar: ['m7 15 5 5 5-5M7 9l5-5 5 5'],
  admin: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'],
} as const;

/** Formas que não são caminho (círculos e retângulos), por ícone. */
const EXTRAS: Partial<Record<keyof typeof ICONES, { circulos?: [number, number, number][]; retangulos?: [number, number, number, number, number][] }>> = {
  equipe: { circulos: [[9, 7, 4]] },
  assinatura: { retangulos: [[1, 4, 22, 16, 2]] },
  conta: { circulos: [[12, 8, 4]] },
  camera: { circulos: [[12, 13, 4]] },
  cadeado: { retangulos: [[3, 11, 18, 11, 2]] },
  info: { circulos: [[12, 12, 10]] },
};

export type NomeDoIcone = keyof typeof ICONES;

@Component({
  selector: 'app-icone',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg aria-hidden="true" [attr.width]="tamanho()" [attr.height]="tamanho()" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" [attr.stroke-width]="traco()" stroke-linecap="round" stroke-linejoin="round">
      @for (d of caminhos(); track d) { <path [attr.d]="d" /> }
      @for (c of extras().circulos ?? []; track $index) { <circle [attr.cx]="c[0]" [attr.cy]="c[1]" [attr.r]="c[2]" /> }
      @for (r of extras().retangulos ?? []; track $index) {
        <rect [attr.x]="r[0]" [attr.y]="r[1]" [attr.width]="r[2]" [attr.height]="r[3]" [attr.rx]="r[4]" />
      }
    </svg>
  `,
  styles: `:host { display: inline-flex; flex: none; } svg { display: block; }`,
})
export class IconeComponent {
  readonly nome = input.required<NomeDoIcone>();
  readonly tamanho = input(18);
  readonly traco = input(2);

  readonly caminhos = computed(() => ICONES[this.nome()]);
  readonly extras = computed(() => EXTRAS[this.nome()] ?? {});
}
