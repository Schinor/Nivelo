import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { AssinaturaOut } from '../../api/models/assinatura-out';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { mensagemDe } from '../../core/http/erro-da-api';
import { IconeComponent } from '../../shared/icone.component';
import { AssinaturaService, PlanoPago } from './assinatura.service';
import { PLANOS, PlanoDeVitrine, plano as planoDeVitrine } from './planos';

const INTERVALO_DA_CONFIRMACAO_MS = 2000;
const TEMPO_DA_CONFIRMACAO_MS = 30000;

const STATUS: Record<string, string> = {
  active: 'Ativa',
  trialing: 'Em teste',
  past_due: 'Pagamento pendente',
  unpaid: 'Não paga',
  canceled: 'Cancelada',
  incomplete: 'Pagamento incompleto',
  incomplete_expired: 'Expirada',
  paused: 'Pausada',
};

interface Uso {
  rotulo: string;
  atual: number;
  limite: number | null;
}

/**
 * Plano, uso, checkout e portal da empresa ativa. Voltar do checkout não muda nada: quem muda o
 * plano é o webhook, e esta tela só aguarda a confirmação consultando GET /assinatura.
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
      @if (confirmando()) {
        <p class="alerta alerta-info" role="status">Confirmando pagamento…</p>
      }
      @if (confirmado()) {
        <p class="alerta alerta-sucesso" role="status">Pagamento confirmado. Bom trabalho na obra!</p>
      }
      @if (demorou()) {
        <p class="alerta alerta-aviso" role="status">Ainda não recebemos a confirmação do pagamento. Atualize a página em instantes.</p>
      }
      @if (cancelouCheckout()) {
        <p class="alerta alerta-info" role="status">Pagamento não concluído. Nada foi cobrado.</p>
      }
      @if (erro()) {
        <p class="alerta alerta-erro" role="alert">{{ erro() }}</p>
      }

      @if (auth.ehDono() && dados(); as d) {
        <section aria-labelledby="atual-t" class="cartao cartao-g atual">
          <div class="cartao-titulo">
            <h2 id="atual-t">Plano {{ nomeDoPlano(d.plano) }}</h2>
            <span class="selo" [class.selo-atual]="pagamentoEmDia(d)" [class.selo-pendente]="!pagamentoEmDia(d)">{{ rotuloDoStatus(d.status) }}</span>
          </div>
          @if (d.plano !== d.plano_efetivo) {
            <p class="alerta alerta-aviso">
              O pagamento não está em dia, e a empresa está com os limites do Free. Atualize o cartão para voltar ao {{ nomeDoPlano(d.plano) }}. Nenhum diário é apagado.
            </p>
          }
          @if (d.periodo_fim) {
            <p class="sub">{{ d.cancelar_no_fim ? 'Cancelada; vale até ' : 'Renova em ' }}{{ dataCurta(d.periodo_fim) }}.</p>
          }
          <ul class="usos">
            @for (u of usos(); track u.rotulo) {
              <li>
                <div class="uso-linha"><span>{{ u.rotulo }}</span><span class="mono">{{ u.atual }}{{ u.limite === null ? '' : ' / ' + u.limite }}</span></div>
                @if (u.limite !== null) {
                  <div class="barra" aria-hidden="true"><i [class.cheia]="u.atual >= u.limite" [style.width.%]="porcentagem(u)"></i></div>
                } @else {
                  <span class="ajuda">Ilimitado</span>
                }
              </li>
            }
          </ul>
          @if (d.tem_assinatura_vigente) {
            <button type="button" class="btn btn-contorno esquerda" (click)="gerenciar()" [disabled]="redirecionando()">Gerenciar assinatura</button>
          }
        </section>
      }

      <section aria-labelledby="planos-t" class="secao">
        <h2 id="planos-t">Planos</h2>
        <div class="planos">
          @for (p of planos; track p.codigo) {
            <article class="cartao plano" [class.destaque]="p.destaque">
              <div class="cartao-titulo">
                <strong class="nome">{{ p.nome }}</strong>
                @if (eAtual(p)) { <span class="selo selo-atual">Plano atual</span> }
                @else if (p.destaque) { <span class="selo selo-destaque">Recomendado</span> }
              </div>
              <div class="preco"><strong>{{ p.valor }}</strong><span>/mês</span></div>
              <ul>
                @for (i of p.itens; track i) { <li>{{ i }}</li> }
              </ul>
              @if (p.codigo !== 'free' && podeAssinar()) {
                <button type="button" class="btn btn-bloco" [class.btn-primario]="p.destaque" [class.btn-contorno]="!p.destaque"
                        (click)="assinar(p.codigo)" [disabled]="redirecionando()">
                  Assinar {{ p.nome }}
                </button>
              }
            </article>
          }
        </div>
        @if (dados()?.tem_assinatura_vigente) {
          <p class="sub">Para trocar de plano ou cancelar, use Gerenciar assinatura.</p>
        }
        <p class="seguro"><app-icone nome="cadeado" />Pagamento seguro pelo Stripe. Cancele quando quiser: a empresa volta para o Free e nenhum diário é apagado.</p>
      </section>
    </div>
  `,
  styles: `
    .secao { display: flex; flex-direction: column; gap: 16px; }
    .secao h2 { font-size: 22px; }
    .atual h2 { font-size: 20px; }
    .esquerda { align-self: flex-start; }
    .usos { list-style: none; display: flex; flex-direction: column; gap: 14px; }
    .uso-linha { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; margin-bottom: 6px; }
    .planos { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    .plano { padding: 24px; gap: 14px; }
    .plano.destaque { border: 2px solid var(--verde); padding: 23px; }
    .nome { font-family: var(--fonte-titulo); font-size: 20px; }
    .preco { display: flex; align-items: baseline; gap: 6px; }
    .preco strong { font-family: var(--fonte-titulo); font-size: 32px; font-weight: 800; }
    .preco span { color: var(--tinta-3); }
    .plano ul { padding-left: 18px; display: flex; flex-direction: column; gap: 6px; color: var(--tinta-2); }
    .plano .btn { margin-top: auto; }
    .seguro { display: flex; gap: 10px; align-items: center; font-size: 14px; color: var(--tinta-2); }
  `,
})
export class AssinaturaComponent implements OnInit, OnDestroy {
  auth = inject(AuthService);
  private service = inject(AssinaturaService);
  private avisos = inject(AvisosService);
  private rota = inject(ActivatedRoute);

  readonly planos = PLANOS;

  dados = signal<AssinaturaOut | null>(null);
  erro = signal<string | null>(null);
  redirecionando = signal(false);
  confirmando = signal(false);
  confirmado = signal(false);
  demorou = signal(false);
  cancelouCheckout = signal(false);
  private timer?: ReturnType<typeof setTimeout>;

  /** Quem já tem assinatura troca de plano no portal: um segundo checkout cobraria em dobro. */
  readonly podeAssinar = computed(() => {
    const d = this.dados();
    return this.auth.ehDono() && !!d && !d.tem_assinatura_vigente && !this.confirmando();
  });

  readonly usos = computed<Uso[]>(() => {
    const d = this.dados();
    if (!d) return [];
    const usos: Uso[] = [
      { rotulo: 'Obras ativas', atual: d.uso.obras_ativas, limite: d.direitos.max_obras_ativas ?? null },
      { rotulo: 'Fotos na obra com mais fotos', atual: d.uso.fotos_na_obra_mais_cheia, limite: d.direitos.max_fotos_por_obra ?? null },
    ];
    const equipe = d.uso.membros_equipe;
    if (equipe !== null && equipe !== undefined) {
      usos.push({ rotulo: 'Dono e encarregados', atual: equipe, limite: d.direitos.max_membros_equipe ?? null });
    }
    return usos;
  });

  async ngOnInit(): Promise<void> {
    if (!this.auth.ehDono()) return;
    const retorno = this.rota.snapshot.queryParamMap.get('checkout');
    this.cancelouCheckout.set(retorno === 'cancelado');
    await this.carregar();
    if (retorno === 'sucesso' && !this.dados()?.tem_assinatura_vigente) this.aguardarConfirmacao(Date.now());
    else if (retorno === 'sucesso') this.confirmado.set(true);
  }

  ngOnDestroy(): void {
    clearTimeout(this.timer);
  }

  private async carregar(): Promise<void> {
    try {
      this.dados.set(await this.service.consultar());
      this.erro.set(null);
    } catch (e) {
      this.erro.set(mensagemDe(e));
    }
  }

  private aguardarConfirmacao(inicio: number): void {
    this.confirmando.set(true);
    this.timer = setTimeout(async () => {
      await this.carregar();
      if (this.dados()?.tem_assinatura_vigente) {
        this.confirmando.set(false);
        this.confirmado.set(true);
      } else if (Date.now() - inicio >= TEMPO_DA_CONFIRMACAO_MS) {
        this.confirmando.set(false);
        this.demorou.set(true);
      } else {
        this.aguardarConfirmacao(inicio);
      }
    }, INTERVALO_DA_CONFIRMACAO_MS);
  }

  assinar(plano: PlanoDeVitrine['codigo']): void {
    if (plano !== 'free') void this.irPara(() => this.service.urlDoCheckout(plano as PlanoPago));
  }

  gerenciar(): void {
    void this.irPara(() => this.service.urlDoPortal());
  }

  private async irPara(obterUrl: () => Promise<string>): Promise<void> {
    this.redirecionando.set(true);
    try {
      window.location.href = await obterUrl();
    } catch (e) {
      this.redirecionando.set(false);
      this.avisos.erro(mensagemDe(e));
    }
  }

  eAtual(p: PlanoDeVitrine): boolean {
    const d = this.dados();
    return !!d && d.plano === p.codigo;
  }

  pagamentoEmDia(d: AssinaturaOut): boolean {
    return d.plano === d.plano_efetivo;
  }

  nomeDoPlano(codigo: string): string {
    return planoDeVitrine(codigo).nome;
  }

  rotuloDoStatus(status: string): string {
    return STATUS[status] ?? status;
  }

  porcentagem(u: Uso): number {
    return u.limite ? Math.min(100, (u.atual / u.limite) * 100) : 0;
  }

  dataCurta(iso: string): string {
    return new Date(iso.endsWith('Z') ? iso : `${iso}Z`).toLocaleDateString('pt-BR');
  }
}
