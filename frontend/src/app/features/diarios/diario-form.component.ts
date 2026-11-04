import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { DiarioIn } from '../../api/models/diario-in';
import { DiarioOut } from '../../api/models/diario-out';
import { OcorrenciaIn } from '../../api/models/ocorrencia-in';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { CONDICAO, dataLonga, hoje, TEMPO, TEMPO_ICONE, TIPO_OCORRENCIA } from '../../shared/formatos';
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
    <main class="pagina">
      <a class="voltar" [routerLink]="diarioId() ? ['/diarios', diarioId()] : ['/obras', obraId()]">← Voltar</a>
      <h1>{{ titulo() }}</h1>
      @if (revisao()) {
        <p class="alerta alerta-info">
          Este diário já foi publicado e o cliente já o viu. A alteração vira uma <strong>revisão</strong>: o texto
          anterior fica guardado no histórico, com o motivo que você informar.
        </p>
      }

      @if (carregando()) {
        <p class="carregando">Carregando…</p>
      } @else {
        <form class="formulario" (ngSubmit)="salvar(false)" #f="ngForm">
          <div class="campo" [class.invalido]="erro()?.codigo === 'diario-data-futura' || erro()?.codigo === 'diario-duplicado'">
            <label for="data">Dia</label>
            <input id="data" name="data" type="date" [(ngModel)]="diario.data" [max]="hoje" required />
            <span class="ajuda">{{ dataLonga(diario.data) }}</span>
          </div>

          <fieldset class="campo">
            <legend class="rotulo">Clima</legend>
            @for (turno of turnos; track turno.chave) {
              <div class="turno">
                <span class="nome-turno">{{ turno.rotulo }}</span>
                <div class="opcoes">
                  @for (t of tempos; track t) {
                    <label class="opcao">
                      <input type="radio" [name]="'clima-' + turno.chave" [checked]="clima[turno.chave] === t" (change)="clima[turno.chave] = t" />
                      <span>{{ TEMPO_ICONE[t] }} {{ TEMPO[t] }}</span>
                    </label>
                  }
                </div>
              </div>
            }
          </fieldset>

          <fieldset class="campo">
            <legend class="rotulo">Condição de trabalho</legend>
            <div class="opcoes">
              @for (c of condicoes; track c) {
                <label class="opcao">
                  <input type="radio" name="condicao" [value]="c" [(ngModel)]="diario.condicao" />
                  <span>{{ CONDICAO[c] }}</span>
                </label>
              }
            </div>
          </fieldset>

          <div class="campo">
            <label for="efetivo">Efetivo (pessoas trabalhando)</label>
            <div class="contador">
              <button type="button" class="btn" (click)="mudarEfetivo(-1)" aria-label="Menos uma pessoa">−</button>
              <input id="efetivo" name="efetivo" type="number" inputmode="numeric" min="0" max="10000" [(ngModel)]="diario.efetivo" />
              <button type="button" class="btn" (click)="mudarEfetivo(1)" aria-label="Mais uma pessoa">+</button>
            </div>
          </div>

          <div class="campo" [class.invalido]="erro()?.codigo === 'diario-publicar-sem-atividades'">
            <label for="atividades">O que foi feito hoje</label>
            <textarea id="atividades" name="atividades" [(ngModel)]="diario.atividades" maxlength="10000"
                      placeholder="Ex.: contrapiso da cozinha, assentamento do piso do banheiro"></textarea>
            <span class="ajuda">Obrigatório para publicar.</span>
          </div>

          <div class="campo">
            <label for="observacoes">Observações <span class="opcional">(opcional)</span></label>
            <textarea id="observacoes" name="observacoes" [(ngModel)]="diario.observacoes" maxlength="5000" rows="2"></textarea>
          </div>

          <fieldset class="campo">
            <legend class="rotulo">Ocorrências</legend>
            @for (o of ocorrencias; track $index; let i = $index) {
              <div class="cartao ocorrencia">
                <div class="campo">
                  <label [for]="'oc-tipo-' + i">Tipo</label>
                  <select [id]="'oc-tipo-' + i" [name]="'oc-tipo-' + i" [(ngModel)]="o.tipo">
                    @for (t of tiposDeOcorrencia; track t) { <option [value]="t">{{ TIPO_OCORRENCIA[t] }}</option> }
                  </select>
                </div>
                <div class="campo">
                  <label [for]="'oc-desc-' + i">O que aconteceu</label>
                  <input [id]="'oc-desc-' + i" [name]="'oc-desc-' + i" [(ngModel)]="o.descricao" required maxlength="2000" />
                </div>
                <div class="campo">
                  <label [for]="'oc-imp-' + i">Atraso no prazo (dias) <span class="opcional">(opcional)</span></label>
                  <input [id]="'oc-imp-' + i" [name]="'oc-imp-' + i" type="number" inputmode="numeric" min="0" max="365" [(ngModel)]="o.impacto_prazo_dias" />
                </div>
                <button type="button" class="btn btn-pequeno btn-texto" (click)="ocorrencias.splice(i, 1)">Tirar ocorrência</button>
              </div>
            }
            <button type="button" class="btn btn-pequeno" (click)="ocorrencias.push({ tipo: 'chuva', descricao: '', impacto_prazo_dias: null })">
              + Registrar ocorrência
            </button>
          </fieldset>

          @if (!diarioId()) {
            <fieldset class="campo">
              <legend class="rotulo">Fotos</legend>
              <app-seletor-de-fotos (mudou)="fotos = $event" [desabilitado]="salvando()" />
              <span class="ajuda">As fotos são reduzidas no celular antes de enviar (até 1600 px).</span>
            </fieldset>
          }

          @if (revisao()) {
            <div class="campo" [class.invalido]="erro()?.codigo === 'diario-revisao-sem-motivo'">
              <label for="motivo">Motivo da alteração</label>
              <input id="motivo" name="motivo" [(ngModel)]="motivo" required minlength="5" maxlength="500"
                     placeholder="Ex.: faltou contar o ajudante que chegou às 9h" />
              <span class="ajuda">O cliente vê o motivo no histórico de revisões.</span>
            </div>
          }

          @if (erro(); as e) { <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p> }
          @if (progresso()) { <p class="alerta alerta-info" role="status">{{ progresso() }}</p> }

          <div class="acoes-fixas">
            @if (!diarioId()) {
              <button type="button" class="btn btn-primario btn-bloco" [disabled]="salvando() || f.invalid" (click)="salvar(true)">
                Salvar e publicar
              </button>
              <button type="submit" class="btn btn-bloco" [disabled]="salvando() || f.invalid">Salvar rascunho</button>
            } @else {
              <button type="submit" class="btn btn-primario btn-bloco" [disabled]="salvando() || f.invalid || (revisao() && motivo.trim().length < 5)">
                {{ salvando() ? 'Salvando…' : revisao() ? 'Salvar revisão' : 'Salvar' }}
              </button>
            }
          </div>
        </form>
      }
    </main>
  `,
  styles: `
    h1 { margin-bottom: var(--space-3); }
    fieldset { border: 0; }
    legend { margin-bottom: 6px; }
    .turno { display: grid; gap: 6px; margin-bottom: var(--space-2); }
    .nome-turno { font-size: .82rem; color: var(--ink-muted); }
    .contador { display: grid; grid-template-columns: 56px 1fr 56px; gap: var(--space-2); }
    .contador input { text-align: center; font-size: 1.2rem; }
    .contador .btn { padding: 0; font-size: 1.4rem; }
    .ocorrencia { display: grid; gap: var(--space-3); margin-bottom: var(--space-3); }
    .opcional { color: var(--ink-faint); font-weight: 400; }
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
  readonly TEMPO = TEMPO;
  readonly TEMPO_ICONE = TEMPO_ICONE;
  readonly CONDICAO = CONDICAO;
  readonly TIPO_OCORRENCIA = TIPO_OCORRENCIA;
  readonly tempos: Tempo[] = ['ensolarado', 'nublado', 'chuvoso', 'tempestade'];
  readonly condicoes = ['praticavel', 'impraticavel'] as const;
  readonly tiposDeOcorrencia = Object.keys(TIPO_OCORRENCIA) as OcorrenciaIn['tipo'][];
  readonly turnos = [
    { chave: 'manha' as const, rotulo: 'Manhã' },
    { chave: 'tarde' as const, rotulo: 'Tarde' },
  ];

  diario: Required<Pick<DiarioIn, 'data' | 'condicao' | 'efetivo'>> & { atividades: string; observacoes: string } = {
    data: hoje(),
    condicao: 'praticavel',
    efetivo: 0,
    atividades: '',
    observacoes: '',
  };
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
        atividades: d.atividades ?? '',
        observacoes: d.observacoes ?? '',
      };
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

  mudarEfetivo(delta: number): void {
    this.diario.efetivo = Math.max(0, (Number(this.diario.efetivo) || 0) + delta);
  }

  private corpo(): DiarioIn {
    return {
      data: this.diario.data,
      clima: { manha: this.clima.manha, tarde: this.clima.tarde },
      condicao: this.diario.condicao,
      efetivo: Number(this.diario.efetivo) || 0,
      atividades: this.diario.atividades.trim() || null,
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
