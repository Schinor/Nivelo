import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ObraResumoOut } from '../../api/models/obra-resumo-out';
import { AuthService } from '../../core/auth.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { EstadoDeErroComponent } from '../../shared/estado-de-erro.component';
import { diaMes, hojePorExtenso, STATUS_DA_OBRA } from '../../shared/formatos';
import { IconeComponent } from '../../shared/icone.component';
import { CriarEmpresaComponent } from '../conta/criar-empresa.component';
import { ObrasService, StatusObra } from './obras.service';

/** Obras em cartões. Dono vê todas da empresa; encarregado e cliente, as que são membros. */
@Component({
  selector: 'app-lista-de-obras',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, FormsModule, CriarEmpresaComponent, EstadoDeErroComponent, IconeComponent],
  template: `
    @if (auth.semEmpresa()) {
      <app-criar-empresa />
    } @else if (auth.isAdmin()) {
      <div class="pagina pagina-estreita">
        <div class="vazio">
          <span class="icone"><app-icone nome="cadeado" [tamanho]="26" /></span>
          <h2>O admin não lê dados de obras</h2>
          <p>Por privacidade dos clientes, as obras e os diários ficam só com as empresas. Use o Painel e o menu Usuários.</p>
          <a routerLink="/admin" class="btn btn-contorno">Ir para o painel</a>
        </div>
      </div>
    } @else {
      <div class="pagina">
        <header class="cabecalho">
          <div>
            <span class="sobretitulo">{{ hoje }}</span>
            <h1>Obras</h1>
          </div>
          @if (auth.ehDono()) {
            <a class="btn btn-primario" routerLink="/obras/nova"><app-icone nome="mais" [traco]="2.5" />Nova obra</a>
          }
        </header>

        @if (semNenhuma()) {
          @if (auth.ehDono()) {
            <div class="vazio">
              <span class="nivel-vazio" aria-hidden="true"></span>
              <h2>Nenhuma obra ainda</h2>
              <p>Cadastre a sua primeira obra para começar o diário. Leva menos de um minuto.</p>
              <a routerLink="/obras/nova" class="btn btn-primario">Cadastrar primeira obra</a>
            </div>
          } @else {
            <div class="vazio">
              <span class="nivel-vazio" aria-hidden="true"></span>
              <h2>Nenhuma obra por aqui</h2>
              <p>Você ainda não foi incluído em nenhuma obra da {{ auth.contexto()?.empresa_nome }}. Peça ao dono para adicionar você.</p>
            </div>
          }
        } @else {
          <div class="filtros">
            <div class="segmentos" role="tablist" aria-label="Filtrar por situação">
              @for (f of filtros; track f.valor) {
                <button type="button" role="tab" [attr.aria-selected]="status() === f.valor" (click)="status.set(f.valor)">
                  {{ f.rotulo }} <span class="mono">{{ contagem()[f.valor] ?? '' }}</span>
                </button>
              }
            </div>
            <div class="campo busca">
              <label for="busca" class="sr-only">Buscar obra</label>
              <input id="busca" type="search" placeholder="Buscar por nome, cliente ou cidade" [ngModel]="busca()" (ngModelChange)="busca.set($event)" />
            </div>
          </div>

          @if (erro(); as e) {
            <app-estado-de-erro [erro]="e" (tentarDeNovo)="recarregar()" />
          } @else if (obras() === null) {
            <p class="carregando">Carregando obras…</p>
          } @else {
            <div class="grade-cartoes">
              @for (o of filtradas(); track o.id) {
                <div class="celula">
                  <a class="cartao obra" [routerLink]="['/obras', o.id]">
                    <div class="cartao-titulo">
                      <span class="selo" [class]="'selo selo-' + o.status">{{ STATUS[o.status] }}</span>
                    </div>
                    <div class="nome">
                      <strong>{{ o.nome }}</strong>
                      <span>{{ o.cidade }}/{{ o.uf }}</span>
                    </div>
                    <div class="numeros">
                      <div class="numero cliente"><span>Cliente</span><strong>{{ o.cliente_nome }}</strong></div>
                      <div class="numero"><span>{{ o.status === 'concluida' ? 'Previsão era' : 'Entrega' }}</span><strong>{{ diaMes(o.previsao_termino) }}</strong></div>
                    </div>
                    @if (o.status === 'concluida') { <span class="nota">Somente leitura · histórico guardado</span> }
                  </a>
                  @if (o.status === 'ativa' && auth.escreveDiario()) {
                    <a class="btn btn-contorno btn-bloco" [routerLink]="['/obras', o.id, 'diarios', 'novo']">Registrar o dia · {{ o.nome }}</a>
                  }
                </div>
              } @empty {
                <p class="sem-resultado">{{ busca() ? 'Nenhuma obra encontrada para “' + busca() + '”.' : 'Nenhuma obra ' + rotuloVazio() + '.' }}</p>
              }
              @if (auth.ehDono() && status() === 'ativa' && !busca()) {
                <a routerLink="/obras/nova" class="nova">
                  <span class="mais"><app-icone nome="mais" [tamanho]="22" [traco]="2.5" /></span>
                  <strong>Cadastrar nova obra</strong>
                  <span>Nome, endereço e cliente. Menos de um minuto.</span>
                </a>
              }
            </div>
            @if (temMais()) {
              <button class="btn btn-bloco" (click)="carregarMais()" [disabled]="carregando()">Carregar mais</button>
            }
          }
        }
      </div>
    }
  `,
  styles: `
    .filtros { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: center; justify-content: space-between; }
    .segmentos { display: flex; gap: 6px; padding: 4px; border-radius: var(--raio); background: var(--papel-2); overflow-x: auto; max-width: 100%; }
    .segmentos button { flex: none; min-height: 40px; padding: 0 14px; border: 0; border-radius: var(--raio-p); background: transparent; color: var(--tinta-2); }
    .segmentos button[aria-selected='true'] { background: var(--branco); color: var(--tinta); font-weight: 600; }
    .segmentos .mono { color: var(--tinta-3); }
    .busca { flex: 0 1 300px; }
    .busca input { min-height: 44px !important; }
    .celula { display: flex; flex-direction: column; gap: 8px; }
    .obra { padding: 18px; gap: 12px; flex: 1; }
    .nome { display: flex; flex-direction: column; gap: 2px; }
    .nome strong { font-family: var(--fonte-titulo); font-size: 20px; line-height: 1.2; }
    .nome span, .nota { color: var(--tinta-3); font-size: 14px; }
    .obra .numeros { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
    .cliente strong { font-family: var(--fonte); font-weight: 600; }
    .sem-resultado { color: var(--tinta-3); padding: 12px 0; }
    .nova { min-height: 220px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; border: 2px dashed var(--linha-campo);
      border-radius: var(--raio-g); color: var(--tinta-2); text-decoration: none; padding: 24px; text-align: center; font-size: 14px; }
    .nova:hover { border-color: var(--tinta-3); color: var(--tinta-2); }
    .nova strong { color: var(--tinta); font-size: 16px; }
    .mais { width: 48px; height: 48px; border-radius: 24px; background: var(--papel-2); display: flex; align-items: center; justify-content: center; color: var(--tinta); }
  `,
})
export class ListaDeObrasComponent {
  auth = inject(AuthService);
  private servico = inject(ObrasService);

  readonly STATUS = STATUS_DA_OBRA;
  readonly diaMes = diaMes;
  readonly hoje = hojePorExtenso();
  readonly filtros: { valor: StatusObra; rotulo: string }[] = [
    { valor: 'ativa', rotulo: 'Em andamento' },
    { valor: 'pausada', rotulo: 'Pausadas' },
    { valor: 'concluida', rotulo: 'Concluídas' },
  ];

  status = signal<StatusObra>('ativa');
  busca = signal('');
  obras = signal<ObraResumoOut[] | null>(null);
  total = signal<number | null>(null);
  contagem = signal<Partial<Record<StatusObra, number>>>({});
  pagina = signal(1);
  carregando = signal(false);
  erro = signal<ErroDaApi | null>(null);

  temMais = computed(() => (this.obras()?.length ?? 0) < (this.total() ?? 0));
  semNenhuma = computed(() => {
    const c = this.contagem();
    return this.filtros.every((f) => c[f.valor] === 0);
  });
  rotuloVazio = computed(() => ({ ativa: 'em andamento', pausada: 'pausada', concluida: 'concluída' })[this.status()]);
  filtradas = computed(() => {
    const termo = normalizar(this.busca());
    const obras = this.obras() ?? [];
    if (!termo) return obras;
    return obras.filter((o) => normalizar(`${o.nome} ${o.cliente_nome} ${o.cidade}`).includes(termo));
  });

  constructor() {
    // Recarrega ao trocar o filtro ou a empresa ativa
    effect(() => {
      const status = this.status();
      if (this.auth.papel()) void this.carregar(status, 1);
    });
    effect(() => {
      if (this.auth.papel()) void this.contar();
    });
  }

  recarregar(): void {
    void this.carregar(this.status(), 1);
    void this.contar();
  }

  /** Quantas obras em cada situação (para os números das abas e o estado "nenhuma obra"). */
  private async contar(): Promise<void> {
    try {
      const totais = await Promise.all(this.filtros.map((f) => this.servico.listar(f.valor, 1, 1).then((r) => r.total)));
      this.contagem.set(Object.fromEntries(this.filtros.map((f, i) => [f.valor, totais[i]])));
    } catch {
      this.contagem.set({});
    }
  }

  private async carregar(status: StatusObra, pagina: number): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    if (pagina === 1) this.obras.set(null);
    try {
      const r = await this.servico.listar(status, pagina);
      this.obras.set(pagina === 1 ? r.itens : [...(this.obras() ?? []), ...r.itens]);
      this.total.set(r.total);
      this.pagina.set(pagina);
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    } finally {
      this.carregando.set(false);
    }
  }

  carregarMais(): void {
    void this.carregar(this.status(), this.pagina() + 1);
  }
}

function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}
