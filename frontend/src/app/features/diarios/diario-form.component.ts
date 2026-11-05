import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { DiarioIn } from '../../api/models/diario-in';
import { DiarioOut } from '../../api/models/diario-out';
import { OcorrenciaIn } from '../../api/models/ocorrencia-in';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { CONDICAO, dataLonga, hoje, linhas, plural, TIPO_OCORRENCIA } from '../../shared/formatos';
import { ObrasService } from '../obras/obras.service';
import { DiariosService } from './diarios.service';
import { SeletorDeFotosComponent } from './seletor-de-fotos.component';

type Tempo = 'ensolarado' | 'nublado' | 'chuvoso' | 'tempestade';

/**
 * Formulário curto do diário. Três usos:
 * - `/obras/:obraId/diarios/novo`: registra o dia (rascunho), envia as fotos e, se pedido, publica;
 * - `/diarios/:diarioId/editar` com rascunho: edita direto;
 * - `/diarios/:diarioId/editar` com publicado: vira revisão e exige o motivo.
 */
@Component({
  selector: 'app-diario-form',
  imports: [FormsModule, RouterLink, SeletorDeFotosComponent],
  template: `
    <div class="pagina pagina-estreita">
      <header class="topo-form">
        <a class="voltar" [routerLink]="diarioId() ? ['/diarios', diarioId()] : ['/obras', obraId()]" aria-label="Voltar">
          <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </a>
        <div>
          <h1>{{ titulo() }}</h1>
          <span class="sub">{{ nomeDaObra() }}{{ nomeDaObra() ? ' · ' : '' }}<span class="capitalizar">{{ dataLonga(diario.data) }}</span></span>
        </div>
      </header>

      @if (revisao()) {
        <p class="alerta alerta-aviso">
          Este diário já foi publicado. A alteração vira uma <strong>revisão</strong>: a versão atual fica guardada e todos da obra,
          inclusive o cliente, veem o motivo.
        </p>
      }

      @if (carregando()) {
        <p class="carregando">Carregando…</p>
      } @else {
        <form class="formulario" (ngSubmit)="salvar(false)" #f="ngForm">
          @if (revisao()) {
            <section class="cartao" [class.invalido]="erro()?.codigo === 'diario-revisao-sem-motivo'">
              <div class="campo" [class.invalido]="erro()?.codigo === 'diario-revisao-sem-motivo'">
                <label for="motivo">Motivo da revisão (obrigatório)</label>
                <textarea id="motivo" name="motivo" rows="2" [(ngModel)]="motivo" required minlength="5" maxlength="500"
                          placeholder="Ex.: efetivo informado errado"></textarea>
              </div>
            </section>
          }

          <section class="cartao">
            <div class="campo" [class.invalido]="erro()?.codigo === 'diario-data-futura' || erro()?.codigo === 'diario-duplicado'">
              <label for="data">Dia do registro</label>
              <input id="data" name="data" type="date" [(ngModel)]="diario.data" [max]="hoje" required />
              <span class="ajuda">Um diário por dia em cada obra. Não vale data futura.</span>
            </div>
          </section>

          <section class="cartao">
            <h2>Clima</h2>
            @for (turno of turnos; track turno.chave) {
              <fieldset class="campo">
                <legend class="turno">{{ turno.rotulo }}</legend>
                <div class="escolhas" style="--colunas: 4">
                  @for (t of tempos; track t.valor) {
                    <label class="escolha">
                      <input type="radio" [name]="'clima-' + turno.chave" [checked]="clima[turno.chave] === t.valor" (change)="clima[turno.chave] = t.valor" />
                      <span class="alto">{{ t.rotulo }}</span>
                    </label>
                  }
                </div>
              </fieldset>
            }
          </section>

          <section class="cartao">
            <fieldset class="campo">
              <legend><h2>Condição do canteiro</h2></legend>
              <div class="escolhas">
                @for (c of condicoes; track c) {
                  <label class="escolha">
                    <input type="radio" name="condicao" [value]="c" [(ngModel)]="diario.condicao" />
                    <span>{{ CONDICAO[c] }}<small>{{ c === 'praticavel' ? 'Deu para trabalhar' : 'Chuva, falta de material…' }}</small></span>
                  </label>
                }
              </div>
            </fieldset>
          </section>

          <section class="cartao">
            <h2>Efetivo</h2>
            <div class="linha-efetivo">
              <label for="efetivo">Pessoas na obra hoje</label>
              <div class="contador">
                <button type="button" (click)="mudarEfetivo(-1)" aria-label="Diminuir">−</button>
                <input id="efetivo" name="efetivo" type="number" inputmode="numeric" min="0" max="10000" [(ngModel)]="diario.efetivo" aria-live="polite" />
                <button type="button" (click)="mudarEfetivo(1)" aria-label="Aumentar">+</button>
              </div>
            </div>
          </section>

          <section class="cartao" [class.invalido]="erro()?.codigo === 'diario-publicar-sem-atividades'">
            <h2>O que foi feito</h2>
            @if (atividades.length) {
              <ul class="lista-atividades">
                @for (a of atividades; track $index; let i = $index) {
                  <li>
                    <span class="marca-ok" aria-hidden="true">✓</span>
                    <span class="texto">{{ a }}</span>
                    <button type="button" class="tirar" (click)="atividades.splice(i, 1)" [attr.aria-label]="'Tirar a atividade ' + a">✕</button>
                  </li>
                }
              </ul>
            }
            <div class="nova-atividade">
              <label for="nova-at" class="sr-only">Nova atividade</label>
              <input id="nova-at" name="nova-at" class="entrada" [(ngModel)]="novaAtividade" maxlength="300" placeholder="Adicionar atividade"
                     (keydown.enter)="$event.preventDefault(); adicionarAtividade()" />
              <button type="button" class="btn btn-escuro somar" (click)="adicionarAtividade()" aria-label="Adicionar atividade">+</button>
            </div>
            <span class="ajuda">Uma por linha. Obrigatório para publicar.</span>
          </section>

          @if (!diarioId()) {
            <section class="cartao">
              <div class="cartao-titulo"><h2>Fotos</h2><span class="mono ajuda">{{ fotos.length ? plural(fotos.length, 'foto', 'fotos') : 'Nenhuma ainda' }}</span></div>
              <app-seletor-de-fotos (mudou)="fotos = $event" [desabilitado]="salvando()" />
              <span class="ajuda">As fotos são reduzidas no celular antes de enviar, para subir até com sinal fraco.</span>
            </section>
          }

          <section class="cartao">
            <fieldset class="campo">
              <legend><h2>Teve alguma ocorrência?</h2></legend>
              <div class="escolhas">
                <label class="escolha"><input type="radio" name="teve" [checked]="!ocorrencias.length" (change)="ocorrencias = []" /><span>Não</span></label>
                <label class="escolha alerta"><input type="radio" name="teve" [checked]="ocorrencias.length > 0" (change)="novaOcorrencia()" /><span>Sim</span></label>
              </div>
            </fieldset>
            @for (o of ocorrencias; track $index; let i = $index) {
              <div class="ocorrencia">
                <fieldset class="campo">
                  <legend class="rotulo">Tipo</legend>
                  <div class="pilulas quebra">
                    @for (t of tiposDeOcorrencia; track t) {
                      <button type="button" class="pilula" [attr.aria-pressed]="o.tipo === t" (click)="o.tipo = t">{{ TIPO_OCORRENCIA[t] }}</button>
                    }
                  </div>
                </fieldset>
                <div class="campo">
                  <label [for]="'oc-desc-' + i">O que aconteceu</label>
                  <textarea [id]="'oc-desc-' + i" [name]="'oc-desc-' + i" rows="3" [(ngModel)]="o.descricao" required maxlength="2000"></textarea>
                </div>
                <div class="campo atraso">
                  <label [for]="'oc-imp-' + i">Atraso no prazo, em dias <span class="opcional">(opcional)</span></label>
                  <input [id]="'oc-imp-' + i" [name]="'oc-imp-' + i" type="number" inputmode="numeric" min="0" max="365" [(ngModel)]="o.impacto_prazo_dias" />
                </div>
                <button type="button" class="btn btn-pequeno btn-texto" (click)="ocorrencias.splice(i, 1)">Tirar esta ocorrência</button>
              </div>
            }
            @if (ocorrencias.length) {
              <button type="button" class="btn btn-pequeno" (click)="novaOcorrencia()">+ Outra ocorrência</button>
            }
          </section>

          <section class="cartao">
            <div class="campo">
              <label for="observacoes">Observações <span class="opcional">(opcional)</span></label>
              <textarea id="observacoes" name="observacoes" [(ngModel)]="diario.observacoes" maxlength="5000" rows="2"
                        placeholder="Ex.: cura da laje, molhar amanhã às 7h e às 15h"></textarea>
            </div>
          </section>

          @if (erro(); as e) { <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p> }
          @if (progresso()) { <p class="alerta alerta-info" role="status">{{ progresso() }}</p> }

          <div class="acoes-fixas">
            @if (!diarioId()) {
              <button type="submit" class="btn btn-contorno btn-grande" [disabled]="salvando() || f.invalid">Salvar rascunho</button>
              <button type="button" class="btn btn-primario btn-grande" [disabled]="salvando() || f.invalid" (click)="salvar(true)">
                {{ salvando() ? 'Salvando…' : 'Publicar o dia' }}
              </button>
            } @else {
              <a class="btn btn-grande" [routerLink]="['/diarios', diarioId()]">Cancelar</a>
              <button type="submit" class="btn btn-primario btn-grande" [disabled]="salvando() || f.invalid || (revisao() && motivo.trim().length < 5)">
                {{ salvando() ? 'Salvando…' : revisao() ? 'Salvar revisão' : 'Salvar' }}
              </button>
            }
          </div>
        </form>
      }
    </div>
  `,
  styles: `
    .pagina { gap: var(--space-4); }
    .topo-form { display: flex; align-items: center; gap: 8px; }
    .topo-form h1 { font-size: 24px !important; }
    .voltar { width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: var(--raio); color: var(--tinta); flex: none; }
    .voltar:hover { background: var(--papel-2); }
    .topo-form > div { display: flex; flex-direction: column; min-width: 0; }
    .topo-form .sub { font-size: 14px; }
    .cartao { padding: 16px; gap: 12px; }
    .cartao h2 { font-family: var(--fonte); font-size: 16px; font-weight: 600; letter-spacing: 0; }
    .cartao.invalido { border-color: var(--terra); }
    .turno { font-size: 13px; color: var(--tinta-2); margin-bottom: 6px; }
    .alto { min-height: 56px !important; font-size: 13px !important; }
    .linha-efetivo { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .lista-atividades { list-style: none; display: flex; flex-direction: column; gap: 6px; }
    .lista-atividades li { display: flex; gap: 10px; align-items: center; padding: 10px 12px; border-radius: var(--raio); background: var(--papel); }
    .marca-ok { width: 22px; height: 22px; border-radius: 6px; background: var(--verde); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; flex: none; }
    .lista-atividades .texto { flex: 1; min-width: 0; overflow-wrap: anywhere; }
    .tirar { width: 36px; height: 36px; border: 0; border-radius: var(--raio-p); background: transparent; color: var(--tinta-3); flex: none; }
    .tirar:hover { background: var(--papel-2); color: var(--tinta); }
    .nova-atividade { display: flex; gap: 8px; }
    .nova-atividade .entrada { flex: 1; min-width: 0; }
    .somar { width: 48px; padding: 0; font-size: 22px; flex: none; }
    .ocorrencia { display: flex; flex-direction: column; gap: 12px; padding-top: 12px; border-top: 1px solid var(--linha-suave); }
    .pilulas.quebra { flex-wrap: wrap; }
    .atraso input { max-width: 160px; }
  `,
})
export class DiarioFormComponent implements OnInit {
  readonly obraId = input<string>();
  readonly diarioId = input<string>();

  private servico = inject(DiariosService);
  private router = inject(Router);
  private avisos = inject(AvisosService);

  readonly hoje = hoje();
  readonly dataLonga = dataLonga;
  readonly plural = plural;
  readonly CONDICAO = CONDICAO;
  readonly TIPO_OCORRENCIA = TIPO_OCORRENCIA;
  readonly tempos: { valor: Tempo; rotulo: string }[] = [
    { valor: 'ensolarado', rotulo: 'Sol' },
    { valor: 'nublado', rotulo: 'Nublado' },
    { valor: 'chuvoso', rotulo: 'Chuva' },
    { valor: 'tempestade', rotulo: 'Temporal' },
  ];
  readonly condicoes = ['praticavel', 'impraticavel'] as const;
  readonly tiposDeOcorrencia = Object.keys(TIPO_OCORRENCIA) as OcorrenciaIn['tipo'][];
  readonly turnos = [
    { chave: 'manha' as const, rotulo: 'Manhã' },
    { chave: 'tarde' as const, rotulo: 'Tarde' },
  ];

  diario: Required<Pick<DiarioIn, 'data' | 'condicao' | 'efetivo'>> & { observacoes: string } = {
    data: hoje(),
    condicao: 'praticavel',
    efetivo: 0,
    observacoes: '',
  };
  /** As atividades viram uma lista na tela e uma por linha no campo `atividades` da API */
  atividades: string[] = [];
  novaAtividade = '';
  nomeDaObra = signal('');
  private obrasServico = inject(ObrasService);
  clima: { manha: Tempo | null; tarde: Tempo | null } = { manha: null, tarde: null };
  ocorrencias: OcorrenciaIn[] = [];
  fotos: File[] = [];
  motivo = '';

  private original = signal<DiarioOut | null>(null);
  revisao = computed(() => this.original()?.status === 'publicado');
  titulo = computed(() => (!this.diarioId() ? 'Registrar o dia' : this.revisao() ? 'Revisar diário' : 'Editar diário'));
  carregando = signal(false);
  salvando = signal(false);
  erro = signal<ErroDaApi | null>(null);
  progresso = signal<string | null>(null);

  ngOnInit(): void {
    if (this.diarioId()) void this.carregar();
    else if (this.obraId()) void this.buscarNomeDaObra(this.obraId()!);
    // O motivo pode vir do modal "Revisar diário"
    const motivo = history.state?.motivo;
    if (typeof motivo === 'string') this.motivo = motivo;
  }

  private async buscarNomeDaObra(obraId: string): Promise<void> {
    try {
      this.nomeDaObra.set((await this.obrasServico.detalhar(obraId)).nome);
    } catch {
      this.nomeDaObra.set('');
    }
  }

  adicionarAtividade(): void {
    const texto = this.novaAtividade.trim();
    if (!texto) return;
    this.atividades.push(texto);
    this.novaAtividade = '';
  }

  novaOcorrencia(): void {
    this.ocorrencias.push({ tipo: 'chuva', descricao: '', impacto_prazo_dias: null });
  }

  private async carregar(): Promise<void> {
    this.carregando.set(true);
    try {
      const d = await this.servico.detalhar(this.diarioId()!);
      this.original.set(d);
      this.diario = {
        data: d.data,
        condicao: d.condicao as 'praticavel' | 'impraticavel',
        efetivo: d.efetivo,
        observacoes: d.observacoes ?? '',
      };
      this.atividades = linhas(d.atividades);
      void this.buscarNomeDaObra(d.obra_id);
      this.clima = { manha: (d.clima.manha as Tempo) ?? null, tarde: (d.clima.tarde as Tempo) ?? null };
      this.ocorrencias = d.ocorrencias.map((o) => ({
        tipo: o.tipo as OcorrenciaIn['tipo'],
        descricao: o.descricao,
        impacto_prazo_dias: o.impacto_prazo_dias,
      }));
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    } finally {
      this.carregando.set(false);
    }
  }

  /** Inclui o que ficou digitado no campo sem tocar no "+" */
  private todasAsAtividades(): string[] {
    const pendente = this.novaAtividade.trim();
    return pendente ? [...this.atividades, pendente] : this.atividades;
  }

  mudarEfetivo(delta: number): void {
    this.diario.efetivo = Math.max(0, (Number(this.diario.efetivo) || 0) + delta);
  }

  private corpo(): DiarioIn {
    return {
      data: this.diario.data,
      clima: { manha: this.clima.manha, tarde: this.clima.tarde },
      condicao: this.diario.condicao,
      efetivo: Number(this.diario.efetivo) || 0,
      atividades: this.todasAsAtividades().join('\n') || null,
      observacoes: this.diario.observacoes.trim() || null,
      ocorrencias: this.ocorrencias
        .filter((o) => o.descricao.trim())
        .map((o) => ({ ...o, descricao: o.descricao.trim(), impacto_prazo_dias: o.impacto_prazo_dias ?? null })),
    };
  }

  async salvar(publicar: boolean): Promise<void> {
    this.salvando.set(true);
    this.erro.set(null);
    try {
      const id = this.diarioId();
      if (id) {
        const original = this.original()!;
        await this.servico.editar(id, original.versao, this.corpo(), this.revisao() ? this.motivo.trim() : null);
        this.avisos.sucesso(this.revisao() ? 'Revisão registrada.' : 'Diário salvo.');
        await this.router.navigate(['/diarios', id]);
        return;
      }
      let diario = await this.servico.registrar(this.obraId()!, this.corpo());
      const falhas = await this.enviarFotos(diario.id);
      if (publicar && falhas === 0) {
        diario = await this.servico.detalhar(diario.id);
        try {
          await this.servico.publicar(diario.id, diario.versao);
        } catch (e) {
          this.avisos.erro(`Diário salvo como rascunho. ${paraErroDaApi(e).mensagem}`);
          await this.router.navigate(['/diarios', diario.id]);
          return;
        }
      }
      if (falhas) {
        this.avisos.erro(`Diário salvo, mas ${falhas} foto(s) não foram enviadas. Tente de novo pela tela do diário.`);
      } else {
        this.avisos.sucesso(publicar ? 'Diário publicado. O cliente já pode ver.' : 'Rascunho salvo.');
      }
      await this.router.navigate(['/diarios', diario.id]);
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    } finally {
      this.salvando.set(false);
      this.progresso.set(null);
    }
  }

  /** Envia uma por vez (sinal fraco no canteiro). Devolve quantas falharam. */
  private async enviarFotos(diarioId: string): Promise<number> {
    let falhas = 0;
    for (const [i, arquivo] of this.fotos.entries()) {
      this.progresso.set(`Enviando foto ${i + 1} de ${this.fotos.length}…`);
      try {
        await this.servico.enviarFoto(diarioId, arquivo, null);
      } catch {
        falhas++;
      }
    }
    return falhas;
  }
}
