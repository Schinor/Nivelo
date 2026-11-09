import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { EventoNoPainelOut } from '../../../api/models/evento-no-painel-out';
import { MetricasOut } from '../../../api/models/metricas-out';
import { mensagemDe } from '../../../core/http/erro-da-api';
import { PainelService } from './painel.service';

/** Visão da plataforma para o admin: cobrança, contas e auditoria, sem nenhum dado de obra. */
@Component({
  selector: 'app-painel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe],
  template: `
    <div class="pagina">
      <header class="cabecalho">
        <div>
          <span class="sobretitulo">Admin da plataforma</span>
          <h1>Painel</h1>
          <p class="sub">Cobrança em modo de teste do Stripe. O admin não lê dados de obras.</p>
        </div>
        <button type="button" class="btn btn-contorno btn-pequeno" [disabled]="carregando()" (click)="carregar()">Atualizar</button>
      </header>

      @if (erro()) { <p class="alerta alerta-erro" role="alert">{{ erro() }}</p> }
      @if (carregando() && !dados()) { <p class="carregando">Carregando…</p> }

      @if (dados(); as d) {
        @if (d.usuarios_total === null) {
          <p class="alerta alerta-aviso" role="status">O serviço de contas não respondeu. Usuários e nomes ficam de fora até ele voltar.</p>
        }

        <section class="indicadores" aria-label="Indicadores da plataforma">
          <div class="cartao indicador">
            <span class="rotulo-mini">MRR de teste</span>
            <strong class="valor">{{ d.mrr_formatado }}</strong>
            <span class="ajuda">Soma das assinaturas pagas ativas</span>
          </div>
          <div class="cartao indicador">
            <span class="rotulo-mini">Assinaturas ativas</span>
            <strong class="valor">{{ d.assinaturas_ativas }}</strong>
            <span class="ajuda">Planos pagos com status ativo</span>
          </div>
          <div class="cartao indicador">
            <span class="rotulo-mini">Inadimplentes</span>
            <strong class="valor">{{ d.inadimplentes }}</strong>
            <span class="ajuda">Pagamento pendente ou não pago</span>
          </div>
          <div class="cartao indicador">
            <span class="rotulo-mini">Empresas e usuários</span>
            <strong class="valor">{{ d.empresas_total }} <small>/ {{ d.usuarios_total ?? '—' }}</small></strong>
            <span class="ajuda">Admin não entra na conta</span>
          </div>
        </section>

        <section class="cartao cartao-g">
          <h2>Por plano</h2>
          <div class="tabela-rolagem">
            <table class="tabela">
              <thead><tr><th scope="col">Plano</th><th scope="col" class="direita">Empresas</th><th scope="col" class="direita">Usuários</th></tr></thead>
              <tbody>
                @for (p of d.por_plano; track p.plano) {
                  <tr>
                    <td><strong>{{ p.rotulo }}</strong></td>
                    <td class="direita mono">{{ p.empresas }}</td>
                    <td class="direita mono">{{ p.usuarios ?? '—' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          <p class="ajuda">Quem trabalha em empresas de planos diferentes aparece em cada plano.</p>
        </section>

        <section class="cartao cartao-g">
          <h2>Últimos eventos</h2>
          @if (d.eventos === null) {
            <p class="alerta alerta-aviso" role="status">A auditoria não respondeu agora. Tente atualizar em instantes.</p>
          } @else {
            <div class="tabela-rolagem">
              <table class="tabela eventos">
                <thead><tr><th scope="col">Quando</th><th scope="col">Evento</th><th scope="col">Quem</th><th scope="col">Empresa</th></tr></thead>
                <tbody>
                  @for (e of d.eventos; track $index) {
                    <tr>
                      <td class="mono nao-quebra">{{ e.quando | date: 'dd/MM/yyyy HH:mm' }}</td>
                      <td class="mono">{{ e.tipo ?? '—' }}</td>
                      <td>{{ ator(e) }}@if (e.ator_papel) { <span class="ajuda"> · {{ e.ator_papel }}</span> }</td>
                      <td>{{ empresa(e) }}</td>
                    </tr>
                  } @empty {
                    <tr><td colspan="4" class="ajuda">Nenhum evento registrado ainda.</td></tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </section>
      }
    </div>
  `,
  styles: `
    .indicadores { display: grid; gap: var(--space-3); grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
    .indicador { gap: var(--space-1); min-width: 0; }
    .valor { font-family: var(--fonte-mono); font-weight: 500; font-size: 26px; line-height: 1.2; overflow-wrap: anywhere; }
    .valor small { font-size: 18px; color: var(--tinta-3); }
    .direita { text-align: right; }
    .eventos { min-width: 640px; }
    .nao-quebra { white-space: nowrap; }
  `,
})
export class PainelComponent implements OnInit {
  private service = inject(PainelService);

  readonly dados = signal<MetricasOut | null>(null);
  readonly carregando = signal(true);
  readonly erro = signal('');

  ngOnInit(): void {
    void this.carregar();
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    this.erro.set('');
    try {
      this.dados.set(await this.service.consultar());
    } catch (e) {
      this.erro.set(mensagemDe(e));
    } finally {
      this.carregando.set(false);
    }
  }

  ator(e: EventoNoPainelOut): string {
    if (e.ator_nome) return e.ator_nome;
    return e.ator_id === null || e.ator_id === undefined ? '—' : `Usuário ${e.ator_id}`;
  }

  empresa(e: EventoNoPainelOut): string {
    return e.empresa_nome ?? e.empresa_id ?? '—';
  }
}
