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
  templateUrl: './premium-sucesso.component.html',
  styleUrl: './premium.component.css',
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
