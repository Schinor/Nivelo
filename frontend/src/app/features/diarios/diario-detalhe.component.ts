import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ComentarioOut } from '../../api/models/comentario-out';
import { DiarioOut } from '../../api/models/diario-out';
import { FotoOut } from '../../api/models/foto-out';
import { RevisaoOut } from '../../api/models/revisao-out';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { mensagemDe, paraErroDaApi } from '../../core/http/erro-da-api';
import {
  CONDICAO, dataHora, dataLonga, plural, STATUS_DO_DIARIO, TEMPO, TEMPO_ICONE, TIPO_OCORRENCIA,
} from '../../shared/formatos';
import { DiariosService } from './diarios.service';
import { GaleriaComponent } from './galeria.component';
import { SeletorDeFotosComponent } from './seletor-de-fotos.component';

/** Um diário. A mesma tela serve ao cliente: os controles de escrita somem pelo papel (e a API
 * confere: cliente que tentar escrever recebe 403). */
@Component({
  selector: 'app-diario-detalhe',
  imports: [RouterLink, FormsModule, GaleriaComponent, SeletorDeFotosComponent],
  template: `
    <main class="pagina">
      @if (erro()) {
        <a class="voltar" routerLink="/obras">← Obras</a>
        <p class="alerta alerta-erro" role="alert">{{ erro() }}</p>
      } @else if (!diario()) {
        <p class="carregando">Carregando diário…</p>
      } @else {
        @let d = diario()!;
        <a class="voltar" [routerLink]="['/obras', d.obra_id]">← Obra</a>
        <header class="cabecalho">
          <div>
            <h1 class="data">{{ dataLonga(d.data) }}</h1>
            <div class="meta">
              <span class="selo" [class]="'selo selo-' + d.status">{{ STATUS[d.status] }}</span>
              @if (d.publicado_em) { <span>Publicado em {{ dataHora(d.publicado_em) }}</span> }
              @if (d.revisoes) { <span>{{ plural(d.revisoes, 'revisão', 'revisões') }}</span> }
            </div>
          </div>
        </header>

        @if (podeEscrever()) {
          <div class="acoes topo">
            @if (d.status === 'rascunho') {
              <button class="btn btn-primario" (click)="publicar()" [disabled]="ocupado()">Publicar para o cliente</button>
              <a class="btn" [routerLink]="['/diarios', d.id, 'editar']">Editar</a>
              @if (auth.ehDono()) {
                <button class="btn btn-perigo" (click)="remover()" [disabled]="ocupado()">Remover rascunho</button>
              }
            } @else if (podeRevisar()) {
              <a class="btn" [routerLink]="['/diarios', d.id, 'editar']">Revisar (com motivo)</a>
            }
          </div>
          @if (d.status === 'rascunho') {
            <p class="ajuda">O cliente só vê o diário depois de publicado.</p>
          }
        }

        <section class="cartao resumo">
          <dl class="dados">
            <dt>Clima</dt>
            <dd>
              Manhã {{ d.clima.manha ? TEMPO_ICONE[d.clima.manha] + ' ' + TEMPO[d.clima.manha] : '—' }} ·
              Tarde {{ d.clima.tarde ? TEMPO_ICONE[d.clima.tarde] + ' ' + TEMPO[d.clima.tarde] : '—' }}
            </dd>
            <dt>Condição</dt><dd>{{ CONDICAO[d.condicao] }}</dd>
            <dt>Efetivo</dt><dd>{{ plural(d.efetivo, 'pessoa', 'pessoas') }}</dd>
          </dl>
        </section>

        <section>
          <h2>Atividades</h2>
          <p class="texto-longo">{{ d.atividades || 'Nada descrito ainda.' }}</p>
          @if (d.observacoes) {
            <h2>Observações</h2>
            <p class="texto-longo">{{ d.observacoes }}</p>
          }
        </section>

        @if (d.ocorrencias.length) {
          <section>
            <h2>Ocorrências</h2>
            <ul class="lista">
              @for (o of d.ocorrencias; track o.id) {
                <li class="cartao ocorrencia">
                  <strong>⚠️ {{ TIPO_OCORRENCIA[o.tipo] }}</strong>
                  <p>{{ o.descricao }}</p>
                  @if (o.impacto_prazo_dias) { <span class="meta">Atraso: {{ plural(o.impacto_prazo_dias, 'dia', 'dias') }}</span> }
                </li>
              }
            </ul>
          </section>
        }

        <section>
          <h2>Fotos {{ d.fotos.length ? '(' + d.fotos.length + ')' : '' }}</h2>
          @if (d.fotos.length) {
            <app-galeria [fotos]="d.fotos" [podeRemover]="podeEscrever() && d.status === 'rascunho'" (remover)="removerFoto($event)" />
          } @else {
            <p class="ajuda">Nenhuma foto.</p>
          }
          @if (podeEscrever()) {
            <div class="enviar">
              @if (d.status === 'publicado') {
                <p class="ajuda">Fotos enviadas agora aparecem para o cliente marcadas como “adicionada após a publicação”.</p>
              }
              <app-seletor-de-fotos [mostrarPrevias]="false" [desabilitado]="ocupado()" rotulo="Adicionar fotos" (mudou)="enviarFotos($event)" />
              @if (progresso()) { <p class="alerta alerta-info" role="status">{{ progresso() }}</p> }
            </div>
          }
        </section>

        @if (revisoes().length) {
          <section>
            <h2>Histórico de revisões</h2>
            <ol class="lista">
              @for (r of revisoes(); track r.id) {
                <li class="cartao">
                  <div class="meta"><span>{{ dataHora(r.criado_em) }}</span><span>versão {{ r.versao_anterior }} → {{ r.versao_anterior + 1 }}</span></div>
                  <p class="motivo">“{{ r.motivo }}”</p>
                  <details>
                    <summary>Como estava antes</summary>
                    <dl class="dados antes">
                      <dt>Efetivo</dt><dd>{{ antes(r, 'efetivo') }}</dd>
                      <dt>Condição</dt><dd>{{ CONDICAO[antes(r, 'condicao')] }}</dd>
                      <dt>Atividades</dt><dd class="texto-longo">{{ antes(r, 'atividades') }}</dd>
                    </dl>
                  </details>
                </li>
              }
            </ol>
          </section>
        }

        @if (d.status === 'publicado') {
          <section>
            <h2>Comentários</h2>
            @if (comentarios().length === 0) { <p class="ajuda">Nenhum comentário ainda.</p> }
            <ul class="lista comentarios">
              @for (c of comentarios(); track c.id) {
                <li class="cartao" [class.meu]="c.autor_id === auth.usuarioId()">
                  <div class="meta"><strong>{{ c.autor_id === auth.usuarioId() ? 'Você' : 'Participante da obra' }}</strong><span>{{ dataHora(c.criado_em) }}</span></div>
                  <p class="texto-longo">{{ c.texto }}</p>
                </li>
              }
            </ul>
            <form class="formulario comentar" (ngSubmit)="comentar()">
              <div class="campo">
                <label for="comentario" class="sr-only">Comentário</label>
                <textarea id="comentario" name="comentario" rows="2" [(ngModel)]="novoComentario" maxlength="2000" placeholder="Escreva um comentário…"></textarea>
              </div>
              <button type="submit" class="btn btn-primario" [disabled]="ocupado() || !novoComentario.trim()">Comentar</button>
            </form>
          </section>
        }
      }
    </main>
  `,
  styles: `
    .data { text-transform: capitalize; }
    .topo { margin-top: 0; }
    .ajuda { color: var(--ink-faint); font-size: .85rem; margin-top: var(--space-2); }
    section { margin-top: var(--space-6); }
    .resumo { margin-top: var(--space-4); }
    .ocorrencia p { margin: 6px 0; }
    .enviar { margin-top: var(--space-4); display: grid; gap: var(--space-2); }
    .motivo { margin: var(--space-2) 0; font-style: italic; }
    details summary { cursor: pointer; color: var(--ink-muted); min-height: 32px; }
    .antes { margin-top: var(--space-2); font-size: .9rem; }
    .comentarios { margin-bottom: var(--space-3); }
    .comentarios .meu { border-color: var(--gold-soft); }
    .comentar { grid-template-columns: 1fr; }
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
  readonly TEMPO_ICONE = TEMPO_ICONE;
  readonly TIPO_OCORRENCIA = TIPO_OCORRENCIA;
  readonly dataLonga = dataLonga;
  readonly dataHora = dataHora;
  readonly plural = plural;

  diario = signal<DiarioOut | null>(null);
  revisoes = signal<RevisaoOut[]>([]);
  comentarios = signal<ComentarioOut[]>([]);
  erro = signal<string | null>(null);
  ocupado = signal(false);
  progresso = signal<string | null>(null);
  novoComentario = '';

  podeEscrever = computed(() => this.auth.escreveDiario());
  /** Dono revisa qualquer um; encarregado, só os que registrou (a API confere: 403). */
  podeRevisar = computed(() => this.auth.ehDono() || (this.auth.papel() === 'encarregado' && this.diario()?.autor_id === this.auth.usuarioId()));

  ngOnInit(): void {
    void this.carregar();
  }

  /** Um campo do retrato anterior guardado na revisão. */
  antes(r: RevisaoOut, campo: string): string {
    const v = (r.retrato as Record<string, unknown>)[campo];
    return v === null || v === undefined ? '—' : String(v);
  }

  private async carregar(): Promise<void> {
    try {
      const d = await this.servico.detalhar(this.diarioId());
      this.diario.set(d);
      if (d.revisoes) this.revisoes.set(await this.servico.revisoes(d.id));
      if (d.status === 'publicado') this.comentarios.set((await this.servico.comentarios(d.id)).itens);
    } catch (e) {
      this.erro.set(mensagemDe(e));
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
