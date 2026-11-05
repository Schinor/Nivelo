import { Component, OnInit, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ComentarioOut } from '../../api/models/comentario-out';
import { DiarioOut } from '../../api/models/diario-out';
import { FotoOut } from '../../api/models/foto-out';
import { RevisaoOut } from '../../api/models/revisao-out';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { DiarioResumoOut } from '../../api/models/diario-resumo-out';
import { MembroDaEquipeOut } from '../../api/models/membro-da-equipe-out';
import { EstadoDeErroComponent } from '../../shared/estado-de-erro.component';
import {
  CONDICAO, data, dataHora, dataLonga, diaMes, linhas, PAPEL, plural, STATUS_DO_DIARIO, TEMPO, TIPO_OCORRENCIA,
} from '../../shared/formatos';
import { IconeComponent } from '../../shared/icone.component';
import { EquipeService } from '../conta/equipe.service';
import { ObrasService } from '../obras/obras.service';
import { DiariosService } from './diarios.service';
import { GaleriaComponent } from './galeria.component';
import { SeletorDeFotosComponent } from './seletor-de-fotos.component';

/** Um diário. A mesma tela serve ao cliente: os controles de escrita somem pelo papel (e a API
 * confere: cliente que tentar escrever recebe 403). */
@Component({
  selector: 'app-diario-detalhe',
  imports: [RouterLink, FormsModule, GaleriaComponent, SeletorDeFotosComponent, EstadoDeErroComponent, IconeComponent],
  template: `
    <div class="pagina">
      <nav aria-label="Caminho" class="migalhas">
        <a routerLink="/obras">Obras</a><span aria-hidden="true">/</span>
        @if (diario(); as d) {
          <a [routerLink]="['/obras', d.obra_id]">{{ nomeDaObra() || 'Obra' }}</a><span aria-hidden="true">/</span>
          <span>Diário de {{ diaMes(d.data) }}</span>
        }
      </nav>

      @if (erro(); as e) {
        <app-estado-de-erro [erro]="e" recurso="Diário" genero="o" (tentarDeNovo)="carregar()" />
      } @else if (!diario()) {
        <p class="carregando">Carregando diário…</p>
      } @else {
        @let d = diario()!;
        <header class="cabecalho topo">
          <div>
            <span class="sobretitulo">Diário · {{ dataLonga(d.data) }} · {{ data(d.data) }}</span>
            <div class="titulo-com-selo">
              <h1>{{ titulo() }}</h1>
              <span class="selo" [class]="'selo selo-' + (d.revisoes ? 'revisado' : d.status)">{{ d.revisoes ? 'Revisado' : STATUS[d.status] }}</span>
            </div>
            <span class="sub">
              @if (d.publicado_em) { Publicado em {{ dataHora(d.publicado_em) }} } @else { Rascunho: o cliente ainda não vê este dia. }
              @if (d.revisoes) { · {{ plural(d.revisoes, 'revisão', 'revisões') }} }
            </span>
          </div>
          <div class="acoes">
            <button type="button" class="btn" disabled>PDF do RDO (em breve)</button>
            @if (podeEscrever()) {
              @if (d.status === 'rascunho') {
                <a class="btn" [routerLink]="['/diarios', d.id, 'editar']">Editar</a>
                <button class="btn btn-primario" (click)="publicar()" [disabled]="ocupado()">Publicar o dia</button>
              } @else if (podeRevisar()) {
                <button type="button" class="btn btn-contorno" (click)="abrirRevisao()">Revisar diário</button>
              }
            }
          </div>
        </header>

        <div class="com-lateral">
          <div class="principal">
            <section class="cartao resumo" aria-label="Resumo do dia">
              <div><span class="rotulo-mini">Clima · manhã</span><strong>{{ d.clima.manha ? TEMPO[d.clima.manha] : '—' }}</strong></div>
              <div><span class="rotulo-mini">Clima · tarde</span><strong>{{ d.clima.tarde ? TEMPO[d.clima.tarde] : '—' }}</strong></div>
              <div><span class="rotulo-mini">Condição</span><strong>{{ CONDICAO[d.condicao] }}</strong></div>
              <div><span class="rotulo-mini">Efetivo</span><strong class="mono">{{ plural(d.efetivo, 'pessoa', 'pessoas') }}</strong></div>
            </section>

            <section class="cartao">
              <h2>Atividades do dia</h2>
              @if (atividades().length) {
                <ul class="atividades">@for (a of atividades(); track $index) { <li>{{ a }}</li> }</ul>
              } @else {
                <p class="ajuda">Nada descrito ainda. As atividades são obrigatórias para publicar.</p>
              }
              @if (d.observacoes) {
                <div class="observacoes"><span class="rotulo-mini">Observações</span><p class="texto-longo">{{ d.observacoes }}</p></div>
              }
            </section>

            @for (o of d.ocorrencias; track o.id) {
              <section class="faixa-ocorrencia">
                <app-icone nome="alerta" [tamanho]="22" />
                <div>
                  <strong>Ocorrência · {{ TIPO_OCORRENCIA[o.tipo] ?? o.tipo }}</strong>
                  <span>{{ o.descricao }}</span>
                  @if (o.impacto_prazo_dias) { <span class="ajuda">Atraso no prazo: {{ plural(o.impacto_prazo_dias, 'dia', 'dias') }}</span> }
                </div>
              </section>
            }

            <section class="cartao">
              <div class="cartao-titulo"><h2>Fotos</h2><span class="mono ajuda">{{ plural(d.fotos.length, 'foto', 'fotos') }}</span></div>
              @if (d.fotos.length) {
                <app-galeria [fotos]="d.fotos" [podeRemover]="podeEscrever() && d.status === 'rascunho'" (remover)="removerFoto($event)" />
              } @else {
                <p class="ajuda">Nenhuma foto neste dia.</p>
              }
              @if (podeEscrever()) {
                @if (d.status === 'publicado') {
                  <p class="ajuda">Fotos enviadas agora aparecem para o cliente com o selo “Adicionada após a publicação”.</p>
                }
                <app-seletor-de-fotos [mostrarPrevias]="false" [desabilitado]="ocupado()" rotulo="Adicionar fotos" (mudou)="enviarFotos($event)" />
                @if (progresso()) { <p class="alerta alerta-info" role="status">{{ progresso() }}</p> }
              }
            </section>

            @if (d.status === 'publicado') {
              <section class="cartao" aria-labelledby="com-t">
                <h2 id="com-t">Comentários</h2>
                @for (c of comentarios(); track c.id) {
                  <div class="comentario">
                    <span class="avatar" [class.dono]="c.autor_id === auth.usuarioId()">{{ c.autor_id === auth.usuarioId() ? 'EU' : '··' }}</span>
                    <div>
                      <span class="ajuda"><strong class="autor">{{ autorDe(c.autor_id) }}</strong> · {{ dataHora(c.criado_em) }}</span>
                      <p class="texto-longo">{{ c.texto }}</p>
                    </div>
                  </div>
                } @empty {
                  <p class="ajuda">Nenhum comentário ainda.</p>
                }
                <form class="formulario comentar" (ngSubmit)="comentar()">
                  <div class="campo">
                    <label for="comentario">Escrever comentário</label>
                    <textarea id="comentario" name="comentario" rows="3" [(ngModel)]="novoComentario" maxlength="2000"></textarea>
                  </div>
                  <button type="submit" class="btn btn-primario enviar" [disabled]="ocupado() || !novoComentario.trim()">Comentar</button>
                </form>
              </section>
            }

            @if (podeEscrever() && d.status === 'rascunho' && auth.ehDono()) {
              <div class="perigo">
                <button class="btn btn-perigo btn-pequeno" (click)="remover()" [disabled]="ocupado()">Remover rascunho</button>
                <span class="ajuda">Só rascunho pode ser removido. Diário publicado fica para sempre.</span>
              </div>
            }
          </div>

          <aside class="lateral">
            <div class="cartao">
              <strong class="titulo-lateral">Versões</strong>
              <ol class="versoes">
                @if (d.status === 'publicado') {
                  <li>
                    <i class="bolinha"></i>
                    <div><strong>v{{ d.revisoes + 1 }} · {{ d.revisoes ? 'atual' : 'publicada' }}</strong><span>{{ dataHora(d.revisoes ? d.atualizado_em : d.publicado_em) }}</span></div>
                  </li>
                }
                @for (r of revisoes(); track r.id) {
                  <li>
                    <i class="bolinha antiga"></i>
                    <div>
                      <strong>v{{ r.versao_anterior }} → v{{ r.versao_anterior + 1 }}</strong>
                      <span>{{ dataHora(r.criado_em) }}</span>
                      <em>“{{ r.motivo }}”</em>
                      <details>
                        <summary>Como estava antes</summary>
                        <dl class="antes">
                          <dt>Efetivo</dt><dd>{{ antes(r, 'efetivo') }}</dd>
                          <dt>Condição</dt><dd>{{ CONDICAO[antes(r, 'condicao')] ?? antes(r, 'condicao') }}</dd>
                          <dt>Atividades</dt><dd class="texto-longo">{{ antes(r, 'atividades') }}</dd>
                        </dl>
                      </details>
                    </div>
                  </li>
                }
                @if (d.status === 'rascunho') {
                  <li><i class="bolinha antiga"></i><div><strong>Rascunho</strong><span>Criado em {{ dataHora(d.criado_em) }}</span></div></li>
                }
              </ol>
              <p class="ajuda">Toda revisão cria uma nova versão com motivo. A anterior continua visível para todos da obra.</p>
            </div>
            <div class="cartao">
              <strong class="titulo-lateral">Navegar</strong>
              @if (vizinhos().anterior; as a) {
                <a [routerLink]="['/diarios', a.id]" class="navegar">← Diário de {{ diaMes(a.data) }}</a>
              } @else {
                <span class="navegar apagado">Este é o primeiro diário</span>
              }
              @if (vizinhos().proximo; as p) {
                <a [routerLink]="['/diarios', p.id]" class="navegar">Diário de {{ diaMes(p.data) }} →</a>
              } @else {
                <span class="navegar apagado">Próximo diário: ainda não registrado</span>
              }
            </div>
          </aside>
        </div>
      }
    </div>

    @if (revisando()) {
      <div class="fundo" (click)="revisando.set(false)">
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="rev-t" (click)="$event.stopPropagation()">
          <h2 id="rev-t">Revisar diário de {{ diaMes(diario()!.data) }}</h2>
          <p>A versão atual fica guardada no histórico. Todos da obra, inclusive o cliente, verão que houve uma revisão e o motivo.</p>
          <div class="campo">
            <label for="motivo">Motivo da revisão (obrigatório)</label>
            <textarea id="motivo" rows="3" [(ngModel)]="motivo" maxlength="500" placeholder="Ex.: efetivo informado errado"></textarea>
          </div>
          <div class="acoes acoes-direita">
            <button type="button" class="btn" (click)="revisando.set(false)">Cancelar</button>
            <button type="button" class="btn btn-primario" [disabled]="motivo.trim().length < 5" (click)="continuarRevisao()">Continuar para edição</button>
          </div>
        </div>
      </div>
    }
  `,
  styles: `
    .topo { align-items: flex-start; }
    .resumo { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; }
    .resumo > div { display: flex; flex-direction: column; }
    .observacoes { padding-top: 12px; border-top: 1px solid var(--linha-suave); display: flex; flex-direction: column; gap: 4px; }
    .comentario { display: flex; gap: 12px; }
    .comentario > div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .comentario .avatar { width: 36px; height: 36px; }
    .autor { color: var(--tinta); }
    .comentar { padding-top: 12px; border-top: 1px solid var(--linha-suave); }
    .enviar { align-self: flex-end; }
    .perigo { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    .titulo-lateral { font-family: var(--fonte-titulo); font-size: 17px; }
    .versoes { list-style: none; display: flex; flex-direction: column; gap: 14px; }
    .versoes li { display: flex; gap: 12px; }
    .versoes li > div { display: flex; flex-direction: column; min-width: 0; font-size: 13px; }
    .versoes strong { font-size: 14px; }
    .versoes span { color: var(--tinta-3); }
    .versoes em { color: var(--tinta-2); margin-top: 2px; }
    .bolinha { width: 10px; height: 10px; margin-top: 6px; border-radius: 5px; background: var(--verde); flex: none; }
    .bolinha.antiga { background: var(--linha-campo); }
    details summary { cursor: pointer; color: var(--verde-escuro); min-height: 32px; display: flex; align-items: center; }
    .antes { display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; margin-top: 4px; }
    .antes dt { color: var(--tinta-3); }
    .navegar { min-height: 40px; display: flex; align-items: center; }
    .apagado { color: var(--tinta-3); }
    .fundo { position: fixed; inset: 0; z-index: 200; background: rgba(27, 30, 28, .55); display: flex; align-items: center; justify-content: center; padding: 24px; }
    .modal { width: 100%; max-width: 480px; background: var(--branco); border-radius: var(--raio-gg); padding: 28px; display: flex; flex-direction: column; gap: 16px; }
    .modal h2 { font-weight: 800; font-size: 24px; }
    .modal p { color: var(--tinta-2); }
  `,
})
export class DiarioDetalheComponent implements OnInit {
  readonly diarioId = input.required<string>();

  auth = inject(AuthService);
  private servico = inject(DiariosService);
  private avisos = inject(AvisosService);
  private router = inject(Router);

  readonly STATUS = STATUS_DO_DIARIO;
  readonly CONDICAO = CONDICAO;
  readonly TEMPO = TEMPO;
  readonly data = data;
  readonly diaMes = diaMes;
  readonly TIPO_OCORRENCIA = TIPO_OCORRENCIA;
  readonly dataLonga = dataLonga;
  readonly dataHora = dataHora;
  readonly plural = plural;

  diario = signal<DiarioOut | null>(null);
  revisoes = signal<RevisaoOut[]>([]);
  comentarios = signal<ComentarioOut[]>([]);
  erro = signal<ErroDaApi | null>(null);
  nomeDaObra = signal('');
  equipe = signal<MembroDaEquipeOut[]>([]);
  irmaos = signal<DiarioResumoOut[]>([]);
  revisando = signal(false);
  motivo = '';
  private obras = inject(ObrasService);
  private equipeServico = inject(EquipeService);

  readonly atividades = computed(() => linhas(this.diario()?.atividades));
  /** A primeira atividade vira o título, como no caderno de obra */
  readonly titulo = computed(() => this.atividades()[0] ?? `Diário de ${diaMes(this.diario()?.data)}`);
  /** A linha do tempo vem do mais novo para o mais velho */
  readonly vizinhos = computed(() => {
    const lista = this.irmaos();
    const i = lista.findIndex((d) => d.id === this.diario()?.id);
    return { proximo: i > 0 ? lista[i - 1] : null, anterior: i >= 0 && i < lista.length - 1 ? lista[i + 1] : null };
  });
  ocupado = signal(false);
  progresso = signal<string | null>(null);
  novoComentario = '';

  podeEscrever = computed(() => this.auth.escreveDiario());
  /** Dono revisa qualquer um; encarregado, só os que registrou (a API confere: 403). */
  podeRevisar = computed(() => this.auth.ehDono() || (this.auth.papel() === 'encarregado' && this.diario()?.autor_id === this.auth.usuarioId()));

  constructor() {
    // A mesma tela navega entre diários vizinhos: recarrega quando o parâmetro muda
    effect(() => {
      this.diarioId();
      untracked(() => {
        this.diario.set(null);
        this.revisoes.set([]);
        this.comentarios.set([]);
        void this.carregar();
      });
    });
  }

  ngOnInit(): void {
    if (this.auth.ehDono()) this.equipeServico.equipe().then((e) => this.equipe.set(e)).catch(() => undefined);
  }

  autorDe(id: number): string {
    if (id === this.auth.usuarioId()) return 'Você';
    const p = this.equipe().find((m) => m.usuario_id === id);
    return p ? `${p.nome} · ${(PAPEL[p.papel] ?? p.papel).toLowerCase()}` : 'Participante da obra';
  }

  abrirRevisao(): void {
    this.motivo = '';
    this.revisando.set(true);
  }

  continuarRevisao(): void {
    this.revisando.set(false);
    void this.router.navigate(['/diarios', this.diarioId(), 'editar'], { state: { motivo: this.motivo.trim() } });
  }

  /** Um campo do retrato anterior guardado na revisão. */
  antes(r: RevisaoOut, campo: string): string {
    const v = (r.retrato as Record<string, unknown>)[campo];
    return v === null || v === undefined ? '—' : String(v);
  }

  async carregar(): Promise<void> {
    this.erro.set(null);
    try {
      const d = await this.servico.detalhar(this.diarioId());
      this.diario.set(d);
      if (!this.nomeDaObra()) {
        this.obras.detalhar(d.obra_id).then((o) => this.nomeDaObra.set(o.nome)).catch(() => undefined);
        this.servico.listar(d.obra_id, 1, 100).then((r) => this.irmaos.set(r.itens)).catch(() => undefined);
      }
      if (d.revisoes) this.revisoes.set(await this.servico.revisoes(d.id));
      if (d.status === 'publicado') this.comentarios.set((await this.servico.comentarios(d.id)).itens);
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    }
  }

  async publicar(): Promise<void> {
    const d = this.diario()!;
    const ok = await this.avisos.confirmar(
      'Publicar o diário?',
      'O cliente passa a ver este dia. Depois de publicado, qualquer mudança vira uma revisão com motivo.',
      { confirmar: 'Publicar' },
    );
    if (!ok) return;
    await this.executar(async () => {
      this.diario.set(await this.servico.publicar(d.id, d.versao));
      this.avisos.sucesso('Diário publicado.');
    });
  }

  async remover(): Promise<void> {
    const ok = await this.avisos.confirmar('Remover o rascunho?', 'O rascunho e as fotos dele são apagados.', {
      confirmar: 'Remover',
      perigo: true,
    });
    if (!ok) return;
    const obraId = this.diario()!.obra_id;
    await this.executar(async () => {
      await this.servico.remover(this.diarioId());
      this.avisos.sucesso('Rascunho removido.');
      await this.router.navigate(['/obras', obraId]);
    });
  }

  async enviarFotos(arquivos: File[]): Promise<void> {
    await this.executar(async () => {
      let falhas = 0;
      for (const [i, arquivo] of arquivos.entries()) {
        this.progresso.set(`Enviando foto ${i + 1} de ${arquivos.length}…`);
        try {
          await this.servico.enviarFoto(this.diarioId(), arquivo, null);
        } catch (e) {
          falhas++;
          if (paraErroDaApi(e).status === 402) break; // o modal do plano já abriu
        }
      }
      this.progresso.set(null);
      await this.carregar();
      if (falhas) this.avisos.erro(`${falhas} foto(s) não foram enviadas.`);
      else this.avisos.sucesso(arquivos.length > 1 ? 'Fotos enviadas.' : 'Foto enviada.');
    });
  }

  async removerFoto(foto: FotoOut): Promise<void> {
    const ok = await this.avisos.confirmar('Remover a foto?', 'A foto é apagada do diário.', { confirmar: 'Remover', perigo: true });
    if (!ok) return;
    await this.executar(async () => {
      await this.servico.removerFoto(foto.id);
      await this.carregar();
    });
  }

  async comentar(): Promise<void> {
    const texto = this.novoComentario.trim();
    await this.executar(async () => {
      const c = await this.servico.comentar(this.diarioId(), texto);
      this.comentarios.update((cs) => [...cs, c]);
      this.novoComentario = '';
    });
  }

  private async executar(acao: () => Promise<void>): Promise<void> {
    this.ocupado.set(true);
    try {
      await acao();
    } catch (e) {
      const erro = paraErroDaApi(e);
      if (erro.status !== 402) this.avisos.erro(erro.mensagem);
      if (erro.status === 409) await this.carregar();
    } finally {
      this.ocupado.set(false);
      this.progresso.set(null);
    }
  }
}
