import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { AuthService } from '../../core/auth.service';
import { IconeComponent } from '../../shared/icone.component';
import { PLANOS } from './planos';

/**
 * Os planos da empresa. O plano atual e o uso (obras 1/1, fotos 12/30) chegam com o
 * GET /assinatura da Fase 8, e o checkout do Stripe com a Fase 9; até lá a tela mostra os planos
 * e o modal "Limite do plano" (402) traz o dono para cá.
 */
@Component({
  selector: 'app-assinatura',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IconeComponent],
  template: `
    <div class="pagina">
      <header class="cabecalho">
        <div>
          <h1>Assinatura</h1>
          <p class="sub">
            A assinatura é da {{ auth.contexto()?.empresa_nome ?? 'empresa' }} e vale para todas as pessoas da equipe.
            Clientes acompanhando a obra nunca pagam e nunca contam no limite.
          </p>
        </div>
      </header>

      @if (!auth.ehDono()) {
        <p class="alerta alerta-info">Quem assina e gerencia o plano é o dono da empresa.</p>
      }

      <section aria-labelledby="planos-t" class="secao">
        <h2 id="planos-t">Planos</h2>
        <div class="planos">
          @for (p of planos; track p.codigo) {
            <article class="cartao plano" [class.destaque]="p.destaque">
              <div class="cartao-titulo">
                <strong class="nome">{{ p.nome }}</strong>
                @if (p.destaque) { <span class="selo selo-destaque">Recomendado</span> }
              </div>
              <div class="preco"><strong>{{ p.valor }}</strong><span>/mês</span></div>
              <ul>
                @for (i of p.itens; track i) { <li>{{ i }}</li> }
              </ul>
              @if (p.codigo !== 'free' && auth.ehDono()) {
                <button type="button" class="btn btn-bloco" [class.btn-primario]="p.destaque" [class.btn-contorno]="!p.destaque" disabled>
                  Assinar {{ p.nome }} · em breve
                </button>
              }
            </article>
          }
        </div>
        @if (auth.ehDono()) {
          <p class="alerta alerta-aviso">
            A assinatura online está chegando. Enquanto isso, se o plano Free ficar pequeno, conclua ou pause uma obra para
            liberar a vaga.
          </p>
        }
        <p class="seguro"><app-icone nome="cadeado" />Pagamento seguro pelo Stripe. Cancele quando quiser: a empresa volta para o Free e nenhum diário é apagado.</p>
      </section>
    </div>
  `,
  styles: `
    .secao { display: flex; flex-direction: column; gap: 16px; }
    .secao h2 { font-size: 22px; }
    .planos { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    .plano { padding: 24px; gap: 14px; }
    .plano.destaque { border: 2px solid var(--verde); padding: 23px; }
    .nome { font-family: var(--fonte-titulo); font-size: 20px; }
    .preco { display: flex; align-items: baseline; gap: 6px; }
    .preco strong { font-family: var(--fonte-titulo); font-size: 32px; font-weight: 800; }
    .preco span { color: var(--tinta-3); }
    ul { padding-left: 18px; display: flex; flex-direction: column; gap: 6px; color: var(--tinta-2); }
    .plano .btn { margin-top: auto; }
    .seguro { display: flex; gap: 10px; align-items: center; font-size: 14px; color: var(--tinta-2); }
  `,
})
export class AssinaturaComponent {
  auth = inject(AuthService);
  readonly planos = PLANOS;
}
