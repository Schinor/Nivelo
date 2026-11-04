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
    <label class="btn btn-bloco seletor" [class.btn-primario]="destaque()">
      📷 {{ rotulo() }}
      <input type="file" accept="image/*" capture="environment" multiple class="sr-only"
             [disabled]="desabilitado()" (change)="escolher($event)" />
    </label>
    @if (mostrarPrevias() && fotos().length) {
      <ul class="previas">
        @for (f of fotos(); track f.previa; let i = $index) {
          <li>
            <img [src]="f.previa" [alt]="'Foto ' + (i + 1)" />
            <button type="button" class="tirar" (click)="tirar(i)" [attr.aria-label]="'Tirar a foto ' + (i + 1)">✕</button>
          </li>
        }
      </ul>
    }
  `,
  styles: `
    .seletor { cursor: pointer; }
    .previas { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
    .previas li { position: relative; aspect-ratio: 1; }
    .previas img { width: 100%; height: 100%; object-fit: cover; border-radius: var(--radius-md); }
    .tirar { position: absolute; top: 4px; right: 4px; width: 32px; height: 32px; border-radius: 50%; border: 0; background: rgba(0,0,0,.7); color: #fff; }
  `,
})
export class SeletorDeFotosComponent implements OnDestroy {
  readonly rotulo = input('Tirar ou escolher fotos');
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
