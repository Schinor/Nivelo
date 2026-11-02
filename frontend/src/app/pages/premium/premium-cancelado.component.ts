import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PremiumCtaComponent } from '../../components/premium-cta/premium-cta.component';

@Component({
  selector: 'app-premium-cancelado',
  imports: [RouterLink, PremiumCtaComponent],
  template: `
    <div class="premium-container">
      <div class="premium-card">
        <h1>Pagamento cancelado</h1>
        <p>Nenhuma cobrança foi feita. Você continua no plano gratuito e pode assinar quando quiser.</p>
        <div class="acoes">
          <app-premium-cta rotulo="Tentar de novo" />
          <a routerLink="/obras" class="btn-secondary">Voltar às obras</a>
        </div>
      </div>
    </div>
  `,
  styleUrl: './premium.component.css',
})
export class PremiumCanceladoComponent {}
