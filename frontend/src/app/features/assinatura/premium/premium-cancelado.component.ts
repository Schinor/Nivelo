import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-premium-cancelado',
  imports: [RouterLink],
  template: `
    <div class="premium-container">
      <div class="premium-card">
        <h1>Pagamento cancelado</h1>
        <p>Nenhuma cobrança foi feita. Sua empresa continua no plano Free e pode assinar quando quiser.</p>
        <div class="acoes">
          <a routerLink="/assinatura" class="btn-primary">Ver planos</a>
          <a routerLink="/obras" class="btn-secondary">Voltar às obras</a>
        </div>
      </div>
    </div>
  `,
  styleUrl: './premium.component.css',
})
export class PremiumCanceladoComponent {}
