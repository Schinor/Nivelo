import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-premium-cancelado',
  imports: [RouterLink],
  template: `
    <div class="pagina pagina-estreita">
      <div class="vazio branco">
        <span class="icone"><svg aria-hidden="true" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="1" y="4" width="22" height="16" rx="2"/><path d="M1 10h22"/></svg></span>
        <h2>Pagamento cancelado</h2>
        <p>Nenhuma cobrança foi feita. A empresa continua no plano Free e pode assinar quando quiser.</p>
        <div class="acoes"><a routerLink="/assinatura" class="btn btn-primario">Ver planos</a><a routerLink="/obras" class="btn">Voltar para as obras</a></div>
      </div>
    </div>
  `,
})
export class PremiumCanceladoComponent {}
