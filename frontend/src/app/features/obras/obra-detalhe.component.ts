import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DiarioOut } from '../../api/models/diario-out';
import { DiarioResumoOut } from '../../api/models/diario-resumo-out';
import { MembroDaEquipeOut } from '../../api/models/membro-da-equipe-out';
import { ObraOut } from '../../api/models/obra-out';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { EstadoDeErroComponent } from '../../shared/estado-de-erro.component';
import {
  CONDICAO, data, dataLonga, diaDaSemana, diaDoMes, diaMes, hoje, hora, mesAno, plural, STATUS_DA_OBRA, STATUS_DO_DIARIO, TIPO_OCORRENCIA,
} from '../../shared/formatos';
import { IconeComponent } from '../../shared/icone.component';
import { EquipeService } from '../conta/equipe.service';
import { DiariosService } from '../diarios/diarios.service';
import { GaleriaComponent } from '../diarios/galeria.component';
import { HistoricoDaObraComponent } from './historico-da-obra.component';
import { ObrasService, StatusObra } from './obras.service';
import { PessoasDaObraComponent } from './pessoas-da-obra.component';

type Aba = 'diarios' | 'fotos' | 'ocorrencias' | 'pessoas' | 'historico';

interface OcorrenciaDaObra {
  id: string;
  tipo: string;
  descricao: string;
  impacto: number | null;
  diarioId: string;
  data: string;
}

/**
 * Uma obra em abas: Diários (linha do tempo), Fotos, Ocorrências e, só para o dono, Pessoas da
 * obra e Histórico. Cliente e encarregado veem a mesma rota sem os controles do dono (a API
 * confere: 403). Fotos e ocorrências saem dos diários já carregados na linha do tempo.
 */
@Component({
  selector: 'app-obra-detalhe',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, EstadoDeErroComponent, IconeComponent, GaleriaComponent, PessoasDaObraComponent, HistoricoDaObraComponent],
  template: `
    <div class="pagina">
      <nav aria-label="Caminho" class="migalhas"><a routerLink="/obras">Obras</a><span aria-hidden="true">/</span><span>{{ obra()?.nome ?? '…' }}</span></nav>

      @if (erro(); as e) {
        <app-estado-de-erro [erro]="e" recurso="Obra" (tentarDeNovo)="carregarTudo()" />
      } @else if (!obra()) {
        <p class="carregando">Carregando obra…</p>
      } @else {
        @let o = obra()!;
        <header class="cabecalho topo-obra">
          <div>
            <div class="titulo-com-selo">
              <h1>{{ o.nome }}</h1>
              <span class="selo" [class]="'selo selo-' + o.status">{{ STATUS[o.status] }}</span>
            </div>
            <span class="sub">{{ o.endereco.logradouro }} · {{ o.endereco.cidade }}/{{ o.endereco.uf }} · Cliente: {{ o.cliente_nome }}</span>
          </div>
          <div class="acoes">
            @if (auth.ehDono()) {
              <a class="btn" [routerLink]="['/obras', o.id, 'editar']">Editar obra</a>
            }
            @if (auth.escreveDiario() && o.status === 'ativa') {
              @if (diarioDeHoje(); as d) {
                <a class="btn btn-primario" [routerLink]="['/diarios', d.id]">Abrir o diário de hoje</a>
              } @else {
                <a class="btn btn-primario" [routerLink]="['/obras', o.id, 'diarios', 'novo']"><app-icone nome="mais" [traco]="2.5" />Registrar o dia de hoje</a>
              }
            }
          </div>
        </header>

        <div class="abas" role="tablist" aria-label="Seções da obra">
          @for (a of abas(); track a.id) {
            <button type="button" role="tab" class="aba" [id]="'aba-' + a.id" [attr.aria-selected]="aba() === a.id"
                    [attr.aria-controls]="'painel-' + a.id" (click)="abrir(a.id)">
              {{ a.rotulo }} @if (a.n !== null) { <span class="mono">{{ a.n }}</span> }
            </button>
          }
        </div>

        <div role="tabpanel" [id]="'painel-' + aba()" [attr.aria-labelledby]="'aba-' + aba()">
          @switch (aba()) {
            @case ('diarios') {
              <div class="com-lateral">
                <section class="principal linha-do-tempo" aria-label="Linha do tempo de diários">
                  @if (diarios() === null) {
                    <p class="carregando">Carregando diários…</p>
                  } @else if (diarios()!.length === 0) {
                    <div class="vazio branco">
                      <span class="folhas-vazias" aria-hidden="true"><i></i><i></i><i></i></span>
                      <h2>Nenhum diário nesta obra</h2>
                      @if (auth.escreveDiario() && o.status === 'ativa') {
                        <p>Registre o primeiro dia com clima, equipe, atividades e fotos. O cliente vê quando você publicar.</p>
                        <a [routerLink]="['/obras', o.id, 'diarios', 'novo']" class="btn btn-primario">Registrar o dia de hoje</a>
                      } @else {
                        <p>Aguardando o primeiro diário.</p>
                      }
                    </div>
                  } @else {
                    @for (d of diarios(); track d.id; let i = $index) {
                      @if (i === 0 || mesAno(d.data) !== mesAno(diarios()![i - 1].data)) {
                        <span class="mes">{{ mesAno(d.data) }}</span>
                      }
                      <div class="dia">
                        <div class="data-dia" aria-hidden="true">
                          <span class="mono">{{ diaDaSemana(d.data) }}</span>
                          <strong>{{ diaDoMes(d.data) }}</strong>
                          <i></i>
                        </div>
                        <a class="cartao item" [routerLink]="['/diarios', d.id]" [attr.aria-label]="'Diário de ' + dataLonga(d.data)">
                          <div class="cartao-titulo">
                            <span class="meta-dia">{{ CONDICAO[d.condicao] }} · {{ plural(d.efetivo, 'pessoa', 'pessoas') }}</span>
                            <span class="selo" [class]="'selo selo-' + d.status">{{ STATUS_DIARIO[d.status] }}</span>
                          </div>
                          <strong class="capitalizar">{{ dataLonga(d.data) }}</strong>
                          <div class="meta">
                            <span>{{ nomeDe(d.autor_id) }}@if (d.publicado_em) { · {{ hora(d.publicado_em) }} }</span>
                            <span>{{ d.fotos ? plural(d.fotos, 'foto', 'fotos') : 'Sem fotos' }}</span>
                            <span>{{ d.ocorrencias ? plural(d.ocorrencias, 'ocorrência', 'ocorrências') : 'Sem ocorrências' }}</span>
                          </div>
                        </a>
                      </div>
                    }
                    @if ((diarios()?.length ?? 0) < (totalDiarios() ?? 0)) {
                      <button class="btn btn-bloco" (click)="carregarDiarios(paginaDiarios() + 1)">Carregar diários mais antigos</button>
                    }
                  }
                </section>
                <aside class="lateral">
                  <div class="cartao">
                    <strong class="titulo-lateral">Resumo da obra</strong>
                    <dl class="dados">
                      <div><dt>Início</dt><dd>{{ data(o.data_inicio) }}</dd></div>
                      <div><dt>Entrega prevista</dt><dd>{{ data(o.previsao_termino) }}</dd></div>
                      <div><dt>Diários</dt><dd>{{ totalDiarios() ?? '…' }}</dd></div>
                      @if (diasSemDiario() !== null) { <div><dt>Dias sem diário</dt><dd>{{ diasSemDiario() }}</dd></div> }
                    </dl>
                  </div>
                  @if (auth.ehDono()) {
                    <div class="cartao">
                      <strong class="titulo-lateral">Situação da obra</strong>
                      <div class="acoes">
                        @if (o.status === 'ativa') { <button class="btn btn-pequeno" (click)="mudarStatus('pausada')" [disabled]="ocupado()">Pausar</button> }
                        @if (o.status === 'pausada') { <button class="btn btn-pequeno" (click)="mudarStatus('ativa')" [disabled]="ocupado()">Reativar</button> }
                        @if (o.status !== 'concluida') { <button class="btn btn-pequeno" (click)="mudarStatus('concluida')" [disabled]="ocupado()">Concluir</button> }
                        <button class="btn btn-pequeno btn-perigo" (click)="remover()" [disabled]="ocupado()">Remover obra</button>
                      </div>
                      <span class="ajuda">Pausar ou concluir libera a vaga de obra ativa do plano.</span>
                    </div>
                  }
                </aside>
              </div>
            }

            @case ('fotos') {
              <section class="secao" aria-label="Fotos da obra">
                <div class="barra">
                  <div class="pilulas" role="group" aria-label="Filtrar fotos">
                    <button type="button" class="pilula" [attr.aria-pressed]="!soApos()" (click)="soApos.set(false)">Todas</button>
                    <button type="button" class="pilula" [attr.aria-pressed]="soApos()" (click)="soApos.set(true)">Adicionadas após a publicação</button>
                  </div>
                  <span class="mono contagem">{{ plural(totalFotos(), 'foto', 'fotos') }}</span>
                </div>
                @if (detalhes() === null) {
                  <p class="carregando">Carregando fotos…</p>
                } @else {
                  @for (g of gruposDeFotos(); track g.diario.id) {
                    <div class="grupo">
                      <div class="grupo-titulo"><strong class="capitalizar">{{ dataLonga(g.diario.data) }}</strong><a [routerLink]="['/diarios', g.diario.id]">Ver diário</a></div>
                      <app-galeria [fotos]="g.fotos" />
                    </div>
                  } @empty {
                    <p class="ajuda">{{ soApos() ? 'Nenhuma foto foi adicionada depois da publicação.' : 'Nenhuma foto nos diários desta obra ainda.' }}</p>
                  }
                  <p class="ajuda">O selo aparece quando a foto foi enviada depois de o diário ser publicado. A data e o autor do envio ficam no histórico.</p>
                  @if (parcial()) { <p class="ajuda">Mostrando os diários mais recentes. Carregue os mais antigos na aba Diários.</p> }
                }
              </section>
            }

            @case ('ocorrencias') {
              <section class="secao" aria-label="Ocorrências">
                <div class="pilulas" role="group" aria-label="Filtrar por tipo">
                  @for (t of tiposDeOcorrencia(); track t.valor) {
                    <button type="button" class="pilula" [attr.aria-pressed]="tipoOcorrencia() === t.valor" (click)="tipoOcorrencia.set(t.valor)">
                      {{ t.rotulo }} <span class="mono">{{ t.n }}</span>
                    </button>
                  }
                </div>
                @if (detalhes() === null) {
                  <p class="carregando">Carregando ocorrências…</p>
                } @else if (ocorrenciasFiltradas().length === 0) {
                  <p class="ajuda">Nenhuma ocorrência registrada nos diários desta obra.</p>
                } @else {
                  <div class="cartao lista-ocorrencias">
                    @for (oc of ocorrenciasFiltradas(); track oc.id) {
                      <a [routerLink]="['/diarios', oc.diarioId]" class="ocorrencia">
                        <span class="mono quando">{{ diaMes(oc.data) }}</span>
                        <span class="tipo"><span class="selo" [class]="'selo selo-' + oc.tipo">{{ TIPO_OCORRENCIA[oc.tipo] ?? oc.tipo }}</span></span>
                        <span class="texto">
                          <span>{{ oc.descricao }}</span>
                          <span class="ajuda">Diário de {{ diaMes(oc.data) }}@if (oc.impacto) { · atraso de {{ plural(oc.impacto, 'dia', 'dias') }} }</span>
                        </span>
                      </a>
                    }
                  </div>
                }
                @if (parcial()) { <p class="ajuda">Mostrando os diários mais recentes. Carregue os mais antigos na aba Diários.</p> }
              </section>
            }

            @case ('pessoas') {
              <app-pessoas-da-obra [obra]="o" [equipe]="equipe()" (mudou)="carregar()" />
            }

            @case ('historico') {
              <app-historico-da-obra [obraId]="o.id" [equipe]="equipe()" />
            }
          }
        </div>
      }
    </div>
  `,
  styles: `
    .topo-obra { align-items: flex-start; }
    .linha-do-tempo { gap: 0 !important; }
    .mes { font-family: var(--fonte-mono); font-size: 12px; letter-spacing: .08em; color: var(--tinta-3); margin: 4px 0 12px; }
    .dia { display: flex; gap: 12px; }
    @media (min-width: 720px) { .dia { gap: 16px; } }
    .data-dia { width: 48px; flex: none; display: flex; flex-direction: column; align-items: center; }
    .data-dia .mono { font-size: 12px; color: var(--tinta-3); }
    .data-dia strong { font-family: var(--fonte-titulo); font-size: 26px; line-height: 1.1; }
    .data-dia i { flex: 1; width: 2px; background: var(--linha); margin-top: 8px; }
    .item { flex: 1; min-width: 0; margin-bottom: 16px; padding: 18px; }
    .item > strong { font-size: 16px; font-weight: 600; }
    .meta-dia { font-size: 14px; color: var(--tinta-2); }
    .titulo-lateral { font-family: var(--fonte-titulo); font-size: 17px; }
    .secao { display: flex; flex-direction: column; gap: 20px; }
    .barra { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; }
    .contagem { font-size: 13px; color: var(--tinta-2); }
    .grupo { display: flex; flex-direction: column; gap: 10px; }
    .grupo-titulo { display: flex; gap: 10px; align-items: baseline; }
    .grupo-titulo strong { font-family: var(--fonte-titulo); font-size: 17px; }
    .grupo-titulo a { font-size: 14px; }
    .lista-ocorrencias { padding: 0; gap: 0; overflow: hidden; }
    .ocorrencia { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: flex-start; padding: 16px 20px; border-bottom: 1px solid var(--linha-suave); text-decoration: none; color: var(--tinta); }
    .ocorrencia:last-child { border-bottom: 0; }
    .ocorrencia:hover { background: var(--papel); color: var(--tinta); }
    .quando { width: 56px; flex: none; font-size: 14px; }
    .tipo { width: 140px; flex: none; }
    .texto { flex: 1 1 260px; min-width: 0; display: flex; flex-direction: column; }
  `,
})
export class ObraDetalheComponent implements OnInit {
  readonly obraId = input.required<string>();
  /** ?aba=fotos abre direto numa aba */
  readonly abaInicial = input<string | undefined>(undefined, { alias: 'aba' });

  auth = inject(AuthService);
  private obras = inject(ObrasService);
  private diariosServico = inject(DiariosService);
  private equipeServico = inject(EquipeService);
  private avisos = inject(AvisosService);
  private router = inject(Router);

  readonly STATUS = STATUS_DA_OBRA;
  readonly STATUS_DIARIO = STATUS_DO_DIARIO;
  readonly CONDICAO = CONDICAO;
  readonly TIPO_OCORRENCIA = TIPO_OCORRENCIA;
  readonly data = data;
  readonly dataLonga = dataLonga;
  readonly diaDaSemana = diaDaSemana;
  readonly diaDoMes = diaDoMes;
  readonly diaMes = diaMes;
  readonly mesAno = mesAno;
  readonly hora = hora;
  readonly plural = plural;

  obra = signal<ObraOut | null>(null);
  erro = signal<ErroDaApi | null>(null);
  ocupado = signal(false);
  aba = signal<Aba>('diarios');
  diarios = signal<DiarioResumoOut[] | null>(null);
  totalDiarios = signal<number | null>(null);
  paginaDiarios = signal(1);
  equipe = signal<MembroDaEquipeOut[]>([]);
  /** Diários completos (fotos e ocorrências), carregados ao abrir essas abas */
  detalhes = signal<DiarioOut[] | null>(null);
  soApos = signal(false);
  tipoOcorrencia = signal('');

  readonly abas = computed(() => {
    const lista: { id: Aba; rotulo: string; n: number | null }[] = [
      { id: 'diarios', rotulo: 'Diários', n: this.totalDiarios() },
      { id: 'fotos', rotulo: 'Fotos', n: this.diarios() ? this.diarios()!.reduce((s, d) => s + d.fotos, 0) : null },
      { id: 'ocorrencias', rotulo: 'Ocorrências', n: this.diarios() ? this.diarios()!.reduce((s, d) => s + d.ocorrencias, 0) : null },
    ];
    if (this.auth.ehDono()) {
      lista.push({ id: 'pessoas', rotulo: 'Pessoas da obra', n: this.obra()?.membros?.length ?? null });
      lista.push({ id: 'historico', rotulo: 'Histórico', n: null });
    }
    return lista;
  });

  readonly diarioDeHoje = computed(() => this.diarios()?.find((d) => d.data === hoje()) ?? null);
  readonly parcial = computed(() => (this.diarios()?.length ?? 0) < (this.totalDiarios() ?? 0));
  readonly diasSemDiario = computed(() => {
    const ultimo = this.diarios()?.[0]?.data;
    if (!ultimo || this.obra()?.status !== 'ativa') return null;
    const [a, m, d] = ultimo.split('-').map(Number);
    const agora = new Date();
    const dias = Math.floor((new Date(agora.getFullYear(), agora.getMonth(), agora.getDate()).getTime() - new Date(a, m - 1, d).getTime()) / 86_400_000);
    return Math.max(0, dias);
  });

  readonly gruposDeFotos = computed(() =>
    (this.detalhes() ?? [])
      .map((d) => ({ diario: d, fotos: this.soApos() ? d.fotos.filter((f) => f.adicionada_apos_publicacao) : d.fotos }))
      .filter((g) => g.fotos.length),
  );
  readonly totalFotos = computed(() => this.gruposDeFotos().reduce((s, g) => s + g.fotos.length, 0));

  private readonly ocorrencias = computed<OcorrenciaDaObra[]>(() =>
    (this.detalhes() ?? []).flatMap((d) =>
      d.ocorrencias.map((o) => ({ id: o.id, tipo: o.tipo, descricao: o.descricao, impacto: o.impacto_prazo_dias, diarioId: d.id, data: d.data })),
    ),
  );
  readonly tiposDeOcorrencia = computed(() => {
    const todas = this.ocorrencias();
    const tipos = Object.keys(TIPO_OCORRENCIA)
      .map((t) => ({ valor: t, rotulo: TIPO_OCORRENCIA[t], n: todas.filter((o) => o.tipo === t).length }))
      .filter((t) => t.n);
    return [{ valor: '', rotulo: 'Todas', n: todas.length }, ...tipos];
  });
  readonly ocorrenciasFiltradas = computed(() => {
    const t = this.tipoOcorrencia();
    return t ? this.ocorrencias().filter((o) => o.tipo === t) : this.ocorrencias();
  });

  ngOnInit(): void {
    this.carregarTudo();
    const inicial = this.abaInicial() as Aba | undefined;
    if (inicial && ['diarios', 'fotos', 'ocorrencias', 'pessoas', 'historico'].includes(inicial)) this.abrir(inicial);
  }

  carregarTudo(): void {
    this.erro.set(null);
    void this.carregar();
    void this.carregarDiarios(1);
    if (this.auth.ehDono()) {
      this.equipeServico.equipe().then((e) => this.equipe.set(e)).catch(() => this.equipe.set([]));
    }
  }

  abrir(aba: Aba): void {
    if ((aba === 'pessoas' || aba === 'historico') && !this.auth.ehDono()) return;
    this.aba.set(aba);
    if ((aba === 'fotos' || aba === 'ocorrencias') && this.detalhes() === null) void this.carregarDetalhes();
  }

  nomeDe(usuarioId: number): string {
    if (usuarioId === this.auth.usuarioId()) return 'Você';
    return this.equipe().find((p) => p.usuario_id === usuarioId)?.nome ?? 'Equipe da obra';
  }

  async carregar(): Promise<void> {
    try {
      this.obra.set(await this.obras.detalhar(this.obraId()));
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    }
  }

  async carregarDiarios(pagina: number): Promise<void> {
    try {
      const r = await this.diariosServico.listar(this.obraId(), pagina);
      this.diarios.set(pagina === 1 ? r.itens : [...(this.diarios() ?? []), ...r.itens]);
      this.totalDiarios.set(r.total);
      this.paginaDiarios.set(pagina);
      if (this.detalhes() !== null) void this.carregarDetalhes();
    } catch (e) {
      if (!this.erro()) this.avisos.erro(paraErroDaApi(e).mensagem);
      this.diarios.set([]);
    }
  }

  /** Só os diários que têm foto ou ocorrência; os outros não acrescentam nada às abas. */
  private async carregarDetalhes(): Promise<void> {
    const ids = (this.diarios() ?? []).filter((d) => d.fotos || d.ocorrencias).map((d) => d.id);
    try {
      const detalhes = await Promise.all(ids.map((id) => this.diariosServico.detalhar(id)));
      this.detalhes.set(detalhes);
    } catch (e) {
      this.avisos.erro(paraErroDaApi(e).mensagem);
      this.detalhes.set([]);
    }
  }

  async mudarStatus(status: StatusObra): Promise<void> {
    const o = this.obra()!;
    if (status === 'concluida') {
      const ok = await this.avisos.confirmar(
        'Concluir a obra?',
        'Obra concluída fica só para consulta e não muda mais de situação. Os diários continuam guardados.',
        { confirmar: 'Concluir obra' },
      );
      if (!ok) return;
    }
    await this.executar(async () => {
      this.obra.set(await this.obras.alterarStatus(o.id, status, o.versao));
      this.avisos.sucesso(`Obra ${STATUS_DA_OBRA[status].toLowerCase()}.`);
    });
  }

  async remover(): Promise<void> {
    const o = this.obra()!;
    const ok = await this.avisos.confirmar(
      `Remover “${o.nome}”?`,
      'A obra some da lista e libera a vaga do plano. Os diários ficam guardados como histórico.',
      { confirmar: 'Remover obra', perigo: true },
    );
    if (!ok) return;
    await this.executar(async () => {
      await this.obras.remover(o.id);
      this.avisos.sucesso('Obra removida.');
      await this.router.navigate(['/obras']);
    });
  }

  private async executar(acao: () => Promise<void>): Promise<void> {
    this.ocupado.set(true);
    try {
      await acao();
    } catch (e) {
      const erro = paraErroDaApi(e);
      // O 402 já abriu o modal "Limite do plano"; o resto vira aviso
      if (erro.status !== 402) this.avisos.erro(erro.mensagem);
      if (erro.status === 409) await this.carregar();
    } finally {
      this.ocupado.set(false);
    }
  }
}
