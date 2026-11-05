import { Component, HostListener, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { plano } from '../../features/assinatura/planos';
import { IconeComponent } from '../../shared/icone.component';
import { AvisosService } from '../avisos.service';

/** Aviso rápido, pedido de confirmação e o modal "Limite do plano" (402), para todas as telas. */
@Component({
  selector: 'app-avisos',
  imports: [RouterLink, IconeComponent],
  template: `
    @if (avisos.aviso(); as a) {
      <div class="toast" [class]="'toast toast-' + a.tipo" [attr.role]="a.tipo === 'erro' ? 'alert' : 'status'" aria-live="polite"
           (click)="avisos.aviso.set(null)">
        <span class="toast-icone"><app-icone [nome]="a.tipo === 'erro' ? 'info' : a.tipo === 'sucesso' ? 'escudo' : 'info'" [tamanho]="20" /></span>
        <span>{{ a.texto }}</span>
      </div>
    }

    @if (avisos.confirmacao(); as c) {
      <div class="fundo" (click)="c.responder(false)">
        <div class="modal" role="alertdialog" aria-modal="true" aria-labelledby="confirmacao-titulo" (click)="$event.stopPropagation()">
          <h2 id="confirmacao-titulo">{{ c.titulo }}</h2>
          <p>{{ c.texto }}</p>
          <div class="botoes">
            <button type="button" class="btn" (click)="c.responder(false)">Cancelar</button>
            <button type="button" class="btn" [class.btn-perigo]="c.perigo" [class.cheio]="c.perigo"
                    [class.btn-primario]="!c.perigo" (click)="c.responder(true)">{{ c.confirmar }}</button>
          </div>
        </div>
      </div>
    }

    @if (avisos.limiteDoPlano(); as p) {
      <div class="fundo" (click)="avisos.fecharLimiteDoPlano()">
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="limite-titulo" (click)="$event.stopPropagation()">
          <span class="icone-limite"><app-icone nome="limite" [tamanho]="24" /></span>
          <div class="texto">
            <h2 id="limite-titulo">{{ p.title || 'Limite do plano atingido' }}</h2>
            <p>{{ p.detail }}</p>
          </div>
          <div class="sugestao">
            <div><strong>{{ sugerido().nome }}</strong><span>{{ sugerido().resumo }}</span></div>
            <strong class="valor">{{ sugerido().valor }}<span>/mês</span></strong>
          </div>
          <div class="botoes">
            <button type="button" class="btn" (click)="avisos.fecharLimiteDoPlano()">Agora não</button>
            <a class="btn btn-primario" [routerLink]="p.acao || '/assinatura'" (click)="avisos.fecharLimiteDoPlano()">
              Assinar o {{ sugerido().nome }}
            </a>
          </div>
        </div>
      </div>
    }
  `,
  styles: `
    .toast { position: fixed; left: 50%; bottom: calc(var(--nav-inferior) + 12px); transform: translateX(-50%); z-index: 300; width: min(92vw, 480px);
      display: flex; gap: 12px; align-items: flex-start; padding: 14px 16px; border-radius: 12px; background: var(--tinta); color: var(--escuro-tinta);
      font-size: 15px; box-shadow: var(--sombra-modal); cursor: pointer; }
    .toast-icone { color: var(--ambar); margin-top: 1px; }
    .toast-sucesso .toast-icone { color: var(--menta); }
    @media (min-width: 900px) { .toast { bottom: 24px; } }

    .fundo { position: fixed; inset: 0; z-index: 200; background: rgba(27, 30, 28, .55); display: flex; align-items: center; justify-content: center; padding: 24px; }
    .modal { width: 100%; max-width: 460px; background: var(--branco); border-radius: var(--raio-gg); padding: 28px; display: flex; flex-direction: column; gap: 16px;
      box-shadow: var(--sombra-modal); }
    .modal h2 { font-weight: 800; font-size: 24px; }
    .modal p { color: var(--tinta-2); }
    .texto { display: flex; flex-direction: column; gap: 6px; }
    .icone-limite { width: 48px; height: 48px; border-radius: 12px; background: var(--ambar-claro); display: flex; align-items: center; justify-content: center; }
    .sugestao { padding: 14px; border-radius: 12px; border: 1px solid var(--linha); display: flex; justify-content: space-between; align-items: center; gap: 12px; }
    .sugestao > div { display: flex; flex-direction: column; }
    .sugestao span { font-size: 13px; color: var(--tinta-3); }
    .valor { font-family: var(--fonte-titulo); font-size: 20px; white-space: nowrap; }
    .valor span { font-family: var(--fonte); font-weight: 400; }
    .botoes { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
  `,
})
export class AvisosComponent {
  avisos = inject(AvisosService);

  /** Pro, ou Construtora quando o limite estourado já é o do Pro (equipe de 5). */
  readonly sugerido = computed(() => plano(this.avisos.limiteDoPlano()?.plano_sugerido ?? 'pro'));

  @HostListener('document:keydown.escape')
  fechar(): void {
    this.avisos.confirmacao()?.responder(false);
    this.avisos.fecharLimiteDoPlano();
  }
}
