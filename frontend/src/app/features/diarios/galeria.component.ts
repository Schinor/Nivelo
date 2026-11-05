import { Component, effect, inject, input, output, signal } from '@angular/core';
import { FotoOut } from '../../api/models/foto-out';
import { dataHora, hora } from '../../shared/formatos';
import { DiariosService } from './diarios.service';

/** Fotos do diário. Cada imagem vem por URL pré-assinada (10 min), pedida à API. A foto que
 * entrou depois da publicação aparece marcada, com a data. */
@Component({
  selector: 'app-galeria',
  template: `
    <ul class="galeria">
      @for (f of fotos(); track f.id) {
        <li>
          <button type="button" class="miniatura ph" (click)="ampliar(f)" [attr.aria-label]="'Ampliar ' + (f.legenda || 'foto')">
            @if (urls()[f.id]; as url) {
              <img [src]="url" [alt]="f.legenda || 'Foto do diário'" loading="lazy" />
            }
            @if (f.adicionada_apos_publicacao) {
              <span class="selo selo-apos">Adicionada após a publicação</span>
            }
          </button>
          <span class="legenda">
            {{ f.legenda || 'Foto' }} · {{ f.adicionada_apos_publicacao ? 'enviada ' + dataHora(f.adicionada_em) : hora(f.adicionada_em) }}
          </span>
          @if (podeRemover()) {
            <button type="button" class="btn btn-pequeno btn-texto" (click)="remover.emit(f)">Remover foto</button>
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
        <button type="button" class="btn">Fechar</button>
      </div>
    }
  `,
  styles: `
    .galeria { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
    .galeria li { display: flex; flex-direction: column; gap: 6px; }
    .miniatura { position: relative; aspect-ratio: 4 / 3; padding: 0; border: 0; border-radius: var(--raio); overflow: hidden; }
    .miniatura img { width: 100%; height: 100%; object-fit: cover; }
    .miniatura .selo-apos { position: absolute; left: 8px; top: 8px; right: 8px; padding: 3px 8px; text-align: left; }
    .legenda { font-size: 13px; color: var(--tinta-2); }
    .fundo { position: fixed; inset: 0; z-index: 250; background: rgba(27, 30, 28, .94); display: grid; place-items: center; align-content: center; gap: 12px; padding: 16px; }
    .fundo img { max-width: 100%; max-height: 78vh; object-fit: contain; border-radius: var(--raio); }
    .fundo p { color: var(--escuro-tinta); text-align: center; }
  `,
})
export class GaleriaComponent {
  readonly fotos = input.required<FotoOut[]>();
  readonly podeRemover = input(false);
  readonly remover = output<FotoOut>();

  private servico = inject(DiariosService);
  readonly dataHora = dataHora;
  readonly hora = hora;
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
