import { Component, HostListener, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AvisosService } from '../avisos.service';

/** Aviso rápido, pedido de confirmação e o modal "Limite do plano" (402), para todas as telas. */
@Component({
  selector: 'app-avisos',
  imports: [RouterLink],
  template: `
    @if (avisos.aviso(); as a) {
      <div class="toast" [class]="'toast toast-' + a.tipo" role="status" aria-live="polite" (click)="avisos.aviso.set(null)">
        {{ a.texto }}
      </div>
    }

    @if (avisos.confirmacao(); as c) {
      <div class="fundo" (click)="c.responder(false)"></div>
      <div class="modal" role="alertdialog" aria-modal="true" aria-labelledby="confirmacao-titulo">
        <h2 id="confirmacao-titulo">{{ c.titulo }}</h2>
        <p>{{ c.texto }}</p>
        <div class="botoes">
          <button type="button" class="btn" (click)="c.responder(false)">Cancelar</button>
          <button type="button" class="btn" [class.btn-perigo]="c.perigo" [class.cheio]="c.perigo"
                  [class.btn-primario]="!c.perigo" (click)="c.responder(true)">{{ c.confirmar }}</button>
        </div>
      </div>
    }

    @if (avisos.limiteDoPlano(); as p) {
      <div class="fundo" (click)="avisos.fecharLimiteDoPlano()"></div>
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="limite-titulo">
        <span class="etiqueta">Limite do plano</span>
        <h2 id="limite-titulo">{{ p.title || 'Limite do plano atingido' }}</h2>
        <p>{{ p.detail }}</p>
        @if (p.limite !== undefined) {
          <p class="uso">Uso: <strong>{{ p.atual }} de {{ p.limite }}</strong></p>
        }
        <div class="botoes">
          <button type="button" class="btn" (click)="avisos.fecharLimiteDoPlano()">Agora não</button>
          <a class="btn btn-primario" [routerLink]="p.acao || '/assinatura'" (click)="avisos.fecharLimiteDoPlano()">
            {{ p.plano_sugerido === 'construtora' ? 'Ver o plano Construtora' : 'Assinar o Pro' }}
          </a>
        </div>
      </div>
    }
  `,
  styles: `
    .toast { position: fixed; left: 50%; bottom: 76px; transform: translateX(-50%); z-index: 300; width: min(92vw, 480px);
      padding: 14px 18px; border-radius: var(--radius-md); font-size: .95rem; box-shadow: var(--shadow-card); cursor: pointer; }
    .toast-info { background: var(--surface-400); color: var(--ink); }
    .toast-sucesso { background: #1d4a30; color: #dff5e7; }
    .toast-erro { background: #5a1c20; color: #ffe1e2; }
    @media (min-width: 861px) { .toast { bottom: 24px; } }
    .fundo { position: fixed; inset: 0; z-index: 200; background: rgba(0,0,0,.6); }
    .modal { position: fixed; z-index: 201; left: 50%; top: 50%; transform: translate(-50%, -50%); width: min(92vw, 440px);
      padding: var(--space-6); background: var(--surface-200); border: 1px solid var(--border-strong); border-radius: var(--radius-lg);
      box-shadow: var(--shadow-card); display: grid; gap: var(--space-3); }
    .modal h2 { font-size: 1.2rem; }
    .modal p { color: var(--ink-muted); line-height: 1.5; }
    .etiqueta { justify-self: start; padding: 4px 10px; border-radius: var(--radius-full); background: var(--gold-soft); color: var(--gold);
      font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; }
    .uso strong { color: var(--ink); }
    .botoes { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-2); }
    .botoes .btn { flex: 1 1 140px; }
  `,
})
export class AvisosComponent {
  avisos = inject(AvisosService);

  @HostListener('document:keydown.escape')
  fechar(): void {
    this.avisos.confirmacao()?.responder(false);
    this.avisos.fecharLimiteDoPlano();
  }
}
