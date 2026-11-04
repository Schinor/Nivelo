import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { DiarioResumoOut } from '../../api/models/diario-resumo-out';
import { EventoDoHistoricoOut } from '../../api/models/evento-do-historico-out';
import { MembroDaEquipeOut } from '../../api/models/membro-da-equipe-out';
import { ObraOut } from '../../api/models/obra-out';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { mensagemDe, paraErroDaApi } from '../../core/http/erro-da-api';
import { CONDICAO, data, dataHora, dataLonga, hoje, PAPEL, plural, STATUS_DA_OBRA, STATUS_DO_DIARIO } from '../../shared/formatos';
import { EquipeService } from '../conta/equipe.service';
import { DiariosService } from '../diarios/diarios.service';
import { ObrasService, StatusObra } from './obras.service';

const EVENTOS: Partial<Record<string, string>> = {
  'obra.criada': 'Obra cadastrada',
  'obra.editada': 'Dados da obra alterados',
  'obra.status_alterado': 'Status alterado',
  'obra.removida': 'Obra removida',
  'obra.membro_adicionado': 'Membro adicionado',
  'obra.membro_removido': 'Membro removido',
  'diario.registrado': 'Diário registrado',
  'diario.editado': 'Rascunho editado',
  'diario.publicado': 'Diário publicado',
  'diario.revisado': 'Diário revisado',
  'diario.removido': 'Rascunho removido',
  'ocorrencia.registrada': 'Ocorrência registrada',
  'foto.anexada': 'Foto anexada',
  'foto.anexada_apos_publicacao': 'Foto adicionada após a publicação',
  'foto.removida': 'Foto removida',
  'comentario.registrado': 'Comentário',
};

/** Uma obra e a linha do tempo dos diários. Cliente e encarregado veem sem os controles do dono. */
@Component({
  selector: 'app-obra-detalhe',
  imports: [RouterLink, FormsModule],
  template: `
    <main class="pagina">
      <a class="voltar" routerLink="/obras">← Obras</a>

      @if (erro()) {
        <p class="alerta alerta-erro" role="alert">{{ erro() }}</p>
      } @else if (!obra()) {
        <p class="carregando">Carregando obra…</p>
      } @else {
        @let o = obra()!;
        <header class="cabecalho">
          <div>
            <h1>{{ o.nome }}</h1>
            <div class="meta">
              <span class="selo" [class]="'selo selo-' + o.status">{{ STATUS[o.status] }}</span>
              <span>📍 {{ o.endereco.logradouro }}, {{ o.endereco.cidade }}/{{ o.endereco.uf }}</span>
            </div>
          </div>
        </header>
        <dl class="dados cartao">
          <dt>Cliente</dt><dd>{{ o.cliente_nome }}</dd>
          <dt>Início</dt><dd>{{ data(o.data_inicio) }}</dd>
          <dt>Previsão</dt><dd>{{ data(o.previsao_termino) }}</dd>
        </dl>

        @if (auth.ehDono()) {
          <div class="acoes">
            <a class="btn btn-pequeno" [routerLink]="['/obras', o.id, 'editar']">Editar</a>
            @if (o.status === 'ativa') {
              <button class="btn btn-pequeno" (click)="mudarStatus('pausada')" [disabled]="ocupado()">Pausar</button>
            }
            @if (o.status === 'pausada') {
              <button class="btn btn-pequeno" (click)="mudarStatus('ativa')" [disabled]="ocupado()">Reativar</button>
            }
            @if (o.status !== 'concluida') {
              <button class="btn btn-pequeno" (click)="mudarStatus('concluida')" [disabled]="ocupado()">Concluir</button>
            }
            <button class="btn btn-pequeno btn-perigo" (click)="remover()" [disabled]="ocupado()">Remover</button>
          </div>
        }

        <section>
          <div class="titulo-secao">
            <h2>Diários {{ totalDiarios() !== null ? '(' + totalDiarios() + ')' : '' }}</h2>
          </div>
          @if (auth.escreveDiario()) {
            @if (diarioDeHoje(); as d) {
              <a class="btn btn-primario btn-bloco" [routerLink]="['/diarios', d.id]">Abrir o diário de hoje</a>
            } @else {
              <a class="btn btn-primario btn-bloco" [routerLink]="['/obras', o.id, 'diarios', 'novo']">Registrar o dia de hoje</a>
            }
          }

          @if (diarios() === null) {
            <p class="carregando">Carregando diários…</p>
          } @else if (diarios()!.length === 0) {
            <div class="vazio">
              <p>{{ auth.ehCliente() ? 'Nenhum diário publicado ainda.' : 'Nenhum diário registrado nesta obra.' }}</p>
            </div>
          } @else {
            <ol class="linha-do-tempo">
              @for (d of diarios(); track d.id) {
                <li>
                  <a class="cartao dia" [routerLink]="['/diarios', d.id]">
                    <div class="topo">
                      <strong>{{ dataLonga(d.data) }}</strong>
                      <span class="selo" [class]="'selo selo-' + d.status">{{ STATUS_DIARIO[d.status] }}</span>
                    </div>
                    <div class="meta">
                      <span>{{ data(d.data) }}</span>
                      <span>👷 {{ plural(d.efetivo, 'pessoa', 'pessoas') }}</span>
                      <span>{{ CONDICAO[d.condicao] }}</span>
                      @if (d.fotos) { <span>📷 {{ d.fotos }}</span> }
                      @if (d.ocorrencias) { <span>⚠️ {{ plural(d.ocorrencias, 'ocorrência', 'ocorrências') }}</span> }
                    </div>
                  </a>
                </li>
              }
            </ol>
            @if ((diarios()?.length ?? 0) < (totalDiarios() ?? 0)) {
              <button class="btn btn-bloco" (click)="carregarDiarios(paginaDiarios() + 1)">Carregar mais</button>
            }
          }
        </section>

        @if (auth.ehDono()) {
          <section>
            <h2>Quem acompanha a obra</h2>
            <p class="ajuda">O dono vê todas as obras. Encarregados e clientes só veem as obras em que estão aqui.</p>
            @if (o.membros?.length) {
              <ul class="lista membros">
                @for (m of o.membros; track m.usuario_id) {
                  <li class="cartao membro">
                    <div>
                      <strong>{{ nomeDe(m.usuario_id) }}</strong>
                      <span class="papel">{{ PAPEL[m.papel] }}</span>
                    </div>
                    <button class="btn btn-pequeno btn-texto" (click)="removerMembro(m.usuario_id)" [attr.aria-label]="'Tirar ' + nomeDe(m.usuario_id) + ' da obra'">Tirar</button>
                  </li>
                }
              </ul>
            } @else {
              <p class="vazio">Ninguém além de você acompanha esta obra.</p>
            }
            @if (candidatos().length) {
              <form class="adicionar" (ngSubmit)="adicionarMembro()">
                <div class="campo">
                  <label for="novo-membro">Adicionar alguém da equipe</label>
                  <select id="novo-membro" name="novo" [(ngModel)]="novoMembro">
                    <option [ngValue]="null">Escolha…</option>
                    @for (p of candidatos(); track p.usuario_id) {
                      <option [ngValue]="p.usuario_id">{{ p.nome }} ({{ PAPEL[p.papel] }})</option>
                    }
                  </select>
                </div>
                <button class="btn" type="submit" [disabled]="!novoMembro || ocupado()">Adicionar</button>
              </form>
            }
            <a class="btn btn-texto" routerLink="/equipe">Convidar alguém novo →</a>
          </section>

          <section>
            <h2>Histórico de auditoria</h2>
            @if (historico() === null) {
              <button class="btn btn-pequeno" (click)="carregarHistorico()">Ver o histórico da obra</button>
            } @else if (historico()!.length === 0) {
              <p class="ajuda">Nada registrado ainda (os eventos chegam com alguns segundos de atraso).</p>
            } @else {
              <ol class="historico">
                @for (e of historico(); track e.event_id) {
                  <li>
                    <span class="quando">{{ dataHora(e.ocorrido_em) }}</span>
                    <span>{{ rotuloDoEvento(e) }}{{ e.ator_id ? ' · ' + nomeDe(e.ator_id) : '' }}</span>
                    @if (motivo(e); as m) { <em>“{{ m }}”</em> }
                  </li>
                }
              </ol>
            }
          </section>
        }
      }
    </main>
  `,
  styles: `
    .dados { margin-top: var(--space-2); }
    section { margin-top: var(--space-6); }
    section > .btn-bloco { margin-bottom: var(--space-4); }
    .linha-do-tempo { list-style: none; display: grid; gap: var(--space-3); border-left: 2px solid var(--border-strong); padding-left: var(--space-4); margin-bottom: var(--space-4); }
    .linha-do-tempo li { position: relative; }
    .linha-do-tempo li::before { content: ''; position: absolute; left: calc(-1 * var(--space-4) - 7px); top: 22px; width: 12px; height: 12px; border-radius: 50%; background: var(--gold); border: 2px solid var(--bg); }
    .dia .topo { display: flex; justify-content: space-between; gap: var(--space-2); align-items: center; margin-bottom: var(--space-2); }
    .dia strong { text-transform: capitalize; }
    .ajuda { color: var(--ink-faint); font-size: .85rem; margin-bottom: var(--space-3); }
    .membro { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); padding: var(--space-3) var(--space-4); }
    .membros { list-style: none; margin-bottom: var(--space-3); }
    .papel { margin-left: 8px; color: var(--ink-muted); font-size: .85rem; }
    .adicionar { display: grid; grid-template-columns: 1fr auto; gap: var(--space-2); align-items: end; margin-bottom: var(--space-2); }
    .historico { list-style: none; display: grid; gap: var(--space-2); font-size: .9rem; }
    .historico li { display: grid; gap: 2px; padding: var(--space-2) 0; border-bottom: 1px solid var(--border); }
    .quando { color: var(--ink-faint); font-size: .8rem; }
    .historico em { color: var(--ink-muted); }
  `,
})
export class ObraDetalheComponent implements OnInit {
  readonly obraId = input.required<string>();

  auth = inject(AuthService);
  private obras = inject(ObrasService);
  private diariosServico = inject(DiariosService);
  private equipeServico = inject(EquipeService);
  private avisos = inject(AvisosService);
  private router = inject(Router);

  readonly STATUS = STATUS_DA_OBRA;
  readonly STATUS_DIARIO = STATUS_DO_DIARIO;
  readonly CONDICAO = CONDICAO;
  readonly PAPEL = PAPEL;
  readonly data = data;
  readonly dataLonga = dataLonga;
  readonly dataHora = dataHora;
  readonly plural = plural;

  obra = signal<ObraOut | null>(null);
  erro = signal<string | null>(null);
  ocupado = signal(false);
  diarios = signal<DiarioResumoOut[] | null>(null);
  totalDiarios = signal<number | null>(null);
  paginaDiarios = signal(1);
  equipe = signal<MembroDaEquipeOut[]>([]);
  historico = signal<EventoDoHistoricoOut[] | null>(null);
  novoMembro: number | null = null;

  diarioDeHoje = computed(() => this.diarios()?.find((d) => d.data === hoje()) ?? null);
  candidatos = computed(() => {
    const ja = new Set((this.obra()?.membros ?? []).map((m) => m.usuario_id));
    return this.equipe().filter((p) => p.papel !== 'dono' && !ja.has(p.usuario_id));
  });

  ngOnInit(): void {
    void this.carregar();
    void this.carregarDiarios(1);
    if (this.auth.ehDono()) {
      this.equipeServico.equipe().then((e) => this.equipe.set(e)).catch(() => this.equipe.set([]));
    }
  }

  rotuloDoEvento(e: EventoDoHistoricoOut): string {
    return EVENTOS[e.tipo ?? ''] ?? e.tipo ?? 'Evento';
  }

  motivo(e: EventoDoHistoricoOut): string | null {
    const m = (e.dados as Record<string, unknown> | undefined)?.['motivo'];
    return typeof m === 'string' ? m : null;
  }

  nomeDe(usuarioId: number): string {
    if (usuarioId === this.auth.usuarioId()) return 'Você';
    return this.equipe().find((p) => p.usuario_id === usuarioId)?.nome ?? `Pessoa nº ${usuarioId}`;
  }

  private async carregar(): Promise<void> {
    try {
      this.obra.set(await this.obras.detalhar(this.obraId()));
    } catch (e) {
      this.erro.set(mensagemDe(e));
    }
  }

  async carregarDiarios(pagina: number): Promise<void> {
    try {
      const r = await this.diariosServico.listar(this.obraId(), pagina);
      this.diarios.set(pagina === 1 ? r.itens : [...(this.diarios() ?? []), ...r.itens]);
      this.totalDiarios.set(r.total);
      this.paginaDiarios.set(pagina);
    } catch (e) {
      if (!this.erro()) this.avisos.erro(mensagemDe(e));
      this.diarios.set([]);
    }
  }

  async mudarStatus(status: StatusObra): Promise<void> {
    const o = this.obra()!;
    if (status === 'concluida') {
      const ok = await this.avisos.confirmar(
        'Concluir a obra?',
        'Obra concluída não muda mais de status. Os diários continuam disponíveis para consulta.',
        { confirmar: 'Concluir' },
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

  async adicionarMembro(): Promise<void> {
    const pessoa = this.equipe().find((p) => p.usuario_id === this.novoMembro);
    if (!pessoa) return;
    await this.executar(async () => {
      await this.obras.adicionarMembro(this.obraId(), pessoa.usuario_id, pessoa.papel as 'encarregado' | 'cliente');
      this.novoMembro = null;
      await this.carregar();
      this.avisos.sucesso(`${pessoa.nome} agora acompanha a obra.`);
    });
  }

  async removerMembro(usuarioId: number): Promise<void> {
    const ok = await this.avisos.confirmar('Tirar da obra?', `${this.nomeDe(usuarioId)} deixa de ver esta obra (continua na equipe).`, {
      confirmar: 'Tirar',
    });
    if (!ok) return;
    await this.executar(async () => {
      await this.obras.removerMembro(this.obraId(), usuarioId);
      await this.carregar();
    });
  }

  async carregarHistorico(): Promise<void> {
    await this.executar(async () => this.historico.set(await this.obras.historico(this.obraId())));
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
