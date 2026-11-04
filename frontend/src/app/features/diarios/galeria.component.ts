import { Component, effect, inject, input, output, signal } from '@angular/core';
import { FotoOut } from '../../api/models/foto-out';
import { dataHora } from '../../shared/formatos';
import { DiariosService } from './diarios.service';

/** Fotos do diário. Cada imagem vem por URL pré-assinada (10 min), pedida à API. A foto que
 * entrou depois da publicação aparece marcada, com a data. */
@Component({
  selector: 'app-galeria',
  template: `
    <ul class="galeria">
      @for (f of fotos(); track f.id) {
        <li>
          <button type="button" class="miniatura" (click)="ampliar(f)" [attr.aria-label]="'Ampliar ' + (f.legenda || 'foto')">
            @if (urls()[f.id]; as url) {
              <img [src]="url" [alt]="f.legenda || 'Foto do diário'" loading="lazy" />
            } @else {
              <span class="sem-imagem">…</span>
            }
          </button>
          @if (f.adicionada_apos_publicacao) {
            <span class="selo selo-apos" [title]="'Adicionada em ' + dataHora(f.adicionada_em)">
              Adicionada após a publicação · {{ dataHora(f.adicionada_em) }}
            </span>
          }
          @if (f.legenda) { <span class="legenda">{{ f.legenda }}</span> }
          @if (podeRemover()) {
            <button type="button" class="btn btn-pequeno btn-texto" (click)="remover.emit(f)">Remover</button>
          }
        </li>
      }
    </ul>

    @if (ampliada(); as f) {
      <div class="fundo" (click)="ampliada.set(null)" role="dialog" aria-modal="true" aria-label="Foto ampliada">
        <img [src]="urls()[f.id]" [alt]="f.legenda || 'Foto do diário'" />
        <p>
          {{ f.legenda }}
          @if (f.adicionada_apos_publicacao) { <br /><small>Adicionada após a publicação, em {{ dataHora(f.adicionada_em) }}</small> }
        </p>
      </div>
    }
  `,
  styles: `
    .galeria { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
    .galeria li { display: grid; gap: 6px; align-content: start; }
    .miniatura { aspect-ratio: 1; padding: 0; border: 0; border-radius: var(--radius-md); overflow: hidden; background: var(--surface-300); }
    .miniatura img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .sem-imagem { color: var(--ink-faint); }
    .selo-apos { white-space: normal; font-size: .72rem; line-height: 1.3; }
    .legenda { font-size: .85rem; color: var(--ink-muted); }
    .fundo { position: fixed; inset: 0; z-index: 250; background: rgba(0,0,0,.92); display: grid; place-items: center; align-content: center; gap: var(--space-3); padding: var(--space-4); }
    .fundo img { max-width: 100%; max-height: 80vh; object-fit: contain; }
    .fundo p { color: var(--ink); text-align: center; }
  `,
})
export class GaleriaComponent {
  readonly fotos = input.required<FotoOut[]>();
  readonly podeRemover = input(false);
  readonly remover = output<FotoOut>();

  private servico = inject(DiariosService);
  readonly dataHora = dataHora;
  urls = signal<Record<string, string>>({});
  ampliada = signal<FotoOut | null>(null);

  constructor() {
    effect(() => {
      for (const f of this.fotos()) {
        if (this.urls()[f.id]) continue;
        this.servico
          .urlDaFoto(f.id)
          .then((url) => this.urls.update((u) => ({ ...u, [f.id]: url })))
          .catch(() => undefined);
      }
    });
  }

  ampliar(f: FotoOut): void {
    if (this.urls()[f.id]) this.ampliada.set(f);
  }
}
