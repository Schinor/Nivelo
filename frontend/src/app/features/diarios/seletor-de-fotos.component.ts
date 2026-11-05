import { Component, OnDestroy, input, output, signal } from '@angular/core';

export interface FotoEscolhida {
  arquivo: File;
  previa: string;
}

/**
 * Escolher fotos pela câmera ou pela galeria do celular. `capture="environment"` abre a câmera
 * traseira direto; `multiple` deixa escolher várias da galeria. A compressão acontece no envio.
 */
@Component({
  selector: 'app-seletor-de-fotos',
  template: `
    @if (mostrarPrevias()) {
      <ul class="previas">
        @for (f of fotos(); track f.previa; let i = $index) {
          <li>
            <img [src]="f.previa" [alt]="'Foto ' + (i + 1)" />
            <button type="button" class="tirar" (click)="tirar(i)" [attr.aria-label]="'Tirar a foto ' + (i + 1)">✕</button>
          </li>
        }
        <li>
          <label class="tirar-foto" [class.desabilitado]="desabilitado()">
            <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            {{ rotulo() }}
            <input type="file" accept="image/*" capture="environment" multiple class="sr-only" [disabled]="desabilitado()" (change)="escolher($event)" />
          </label>
        </li>
      </ul>
    } @else {
      <label class="btn btn-bloco" [class.btn-primario]="destaque()" [class.btn-contorno]="!destaque()" [attr.aria-disabled]="desabilitado()">
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
        {{ rotulo() }}
        <input type="file" accept="image/*" capture="environment" multiple class="sr-only" [disabled]="desabilitado()" (change)="escolher($event)" />
      </label>
    }
  `,
  styles: `
    label { cursor: pointer; }
    .previas { list-style: none; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
    @media (min-width: 720px) { .previas { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); } }
    .previas li { position: relative; aspect-ratio: 1; }
    .previas img { width: 100%; height: 100%; object-fit: cover; border-radius: var(--raio); }
    .tirar { position: absolute; top: 4px; right: 4px; width: 32px; height: 32px; border-radius: 50%; border: 0; background: rgba(27, 30, 28, .75); color: #fff; }
    .tirar-foto { height: 100%; border-radius: var(--raio); border: 2px dashed var(--linha-campo); display: flex; flex-direction: column; align-items: center;
      justify-content: center; gap: 4px; font-size: 13px; font-weight: 600; text-align: center; padding: 4px; background: var(--branco); }
    .tirar-foto:focus-within { outline: 3px solid var(--foco); outline-offset: 2px; }
    .desabilitado { opacity: .55; cursor: not-allowed; }
  `,
})
export class SeletorDeFotosComponent implements OnDestroy {
  readonly rotulo = input('Tirar foto');
  readonly destaque = input(false);
  readonly desabilitado = input(false);
  /** Mostrar as prévias aqui (formulário) ou só emitir (envio imediato). */
  readonly mostrarPrevias = input(true);
  readonly mudou = output<File[]>();

  fotos = signal<FotoEscolhida[]>([]);

  escolher(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const novas = Array.from(campo.files ?? []).filter((a) => a.type.startsWith('image/'));
    campo.value = '';
    if (!novas.length) return;
    if (!this.mostrarPrevias()) {
      this.mudou.emit(novas);
      return;
    }
    this.fotos.update((atuais) => [...atuais, ...novas.map((arquivo) => ({ arquivo, previa: URL.createObjectURL(arquivo) }))]);
    this.mudou.emit(this.fotos().map((f) => f.arquivo));
  }

  tirar(i: number): void {
    URL.revokeObjectURL(this.fotos()[i].previa);
    this.fotos.update((atuais) => atuais.filter((_, j) => j !== i));
    this.mudou.emit(this.fotos().map((f) => f.arquivo));
  }

  ngOnDestroy(): void {
    this.fotos().forEach((f) => URL.revokeObjectURL(f.previa));
  }
}
