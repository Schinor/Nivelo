import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { EMPTY, Subscription, timer } from 'rxjs';
import { catchError, exhaustMap, first, timeout } from 'rxjs/operators';
import { AuthService } from '../../../core/auth.service';
import { PremiumService } from '../premium.service';

const INTERVALO_MS = 1500;
const TIMEOUT_MS = 15000;

/**
 * Volta do Stripe após o pagamento. Esta página NÃO ativa nada: quem marca o
 * usuário como Premium é o webhook. Aqui só esperamos ele chegar (polling).
 */
@Component({
  selector: 'app-premium-sucesso',
  imports: [RouterLink],
  template: `
    <div class="pagina pagina-estreita">
      <div class="vazio branco" role="status" aria-live="polite">
        @switch (estado()) {
          @case ('processando') {
            <span class="icone"><span class="girando" aria-hidden="true"></span></span>
            <h2>Confirmando o pagamento…</h2>
            <p>O Stripe recebeu o checkout. O plano muda assim que a confirmação da assinatura chegar, o que leva poucos segundos.</p>
          }
          @case ('ativo') {
            <span class="nivel-vazio" aria-hidden="true"></span>
            <h2>Assinatura confirmada</h2>
            <p>O plano da empresa foi atualizado. Os novos limites já valem para toda a equipe.</p>
            <div class="acoes"><a routerLink="/obras" class="btn btn-primario">Ir para as obras</a><a routerLink="/assinatura" class="btn">Ver a assinatura</a></div>
          }
          @case ('demorando') {
            <span class="icone ambar"><svg aria-hidden="true" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg></span>
            <h2>Quase lá</h2>
            <p>O pagamento foi recebido, mas a confirmação ainda não chegou. Nada foi cobrado em dobro. Atualize a página em instantes.</p>
            <div class="acoes"><a routerLink="/assinatura" class="btn btn-primario">Ver a assinatura</a></div>
          }
        }
      </div>
    </div>
  `,
  styles: `
    .girando { width: 26px; height: 26px; border-radius: 50%; border: 3px solid var(--linha); border-top-color: var(--verde); animation: girar 1s linear infinite; }
    @keyframes girar { to { transform: rotate(360deg); } }
    @media (prefers-reduced-motion: reduce) { .girando { animation: none; } }
  `,
})
export class PremiumSucessoComponent implements OnInit, OnDestroy {
  private premium = inject(PremiumService);
  private auth = inject(AuthService);
  private sub?: Subscription;

  estado = signal<'processando' | 'ativo' | 'demorando'>('processando');

  ngOnInit() {
    this.sub = timer(0, INTERVALO_MS)
      .pipe(
        // exhaustMap, não switchMap: se o status demora mais que o intervalo, o próximo
        // tique não pode cancelar a consulta em andamento (senão nenhuma resposta chega)
        exhaustMap(() => this.premium.status().pipe(catchError(() => EMPTY))),
        first((s) => s.premium),
        // O prazo conta pelo relógio, não pelas respostas: vale mesmo se nenhuma chegar
        timeout({ first: TIMEOUT_MS }),
      )
      .subscribe({
        next: () => {
          this.estado.set('ativo');
          // O JWT não carrega o plano; só atualiza o usuário guardado no navegador
          this.auth.carregarPerfil();
        },
        error: () => this.estado.set('demorando'),
      });
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }
}
