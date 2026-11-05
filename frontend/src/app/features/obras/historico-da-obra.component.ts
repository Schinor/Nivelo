import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { EventoDoHistoricoOut } from '../../api/models/evento-do-historico-out';
import { MembroDaEquipeOut } from '../../api/models/membro-da-equipe-out';
import { AuthService } from '../../core/auth.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { dataHora, PAPEL } from '../../shared/formatos';
import { IconeComponent } from '../../shared/icone.component';
import { ObrasService } from './obras.service';

const EVENTOS: Partial<Record<string, string>> = {
  'obra.criada': 'Obra cadastrada',
  'obra.editada': 'Dados da obra alterados',
  'obra.status_alterado': 'Situação alterada',
  'obra.removida': 'Obra removida',
  'obra.membro_adicionado': 'Pessoa adicionada à obra',
  'obra.membro_removido': 'Pessoa removida da obra',
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

const CATEGORIAS = [
  { valor: '', rotulo: 'Todos' },
  { valor: 'diario', rotulo: 'Diários' },
  { valor: 'foto', rotulo: 'Fotos' },
  { valor: 'membro', rotulo: 'Pessoas' },
  { valor: 'obra', rotulo: 'Obra' },
];

/** Aba "Histórico" (só o dono): os eventos de auditoria da obra, que ninguém edita nem apaga. */
@Component({
  selector: 'app-historico-da-obra',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, IconeComponent],
  template: `
    <section aria-label="Histórico da obra" class="historico">
      <div class="barra">
        <span class="selo"><app-icone nome="cadeado" [tamanho]="14" [traco]="2.2" />Visível só para o dono</span>
        <div class="filtro">
          <label for="evento" class="rotulo">Evento</label>
          <select id="evento" class="entrada" [ngModel]="categoria()" (ngModelChange)="categoria.set($event)">
            @for (c of categorias; track c.valor) { <option [value]="c.valor">{{ c.rotulo }}</option> }
          </select>
        </div>
      </div>

      @if (erro(); as e) {
        <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p>
      } @else if (eventos() === null) {
        <p class="carregando">Carregando o histórico…</p>
      } @else if (filtrados().length === 0) {
        <p class="ajuda">Nada registrado ainda. Os eventos chegam com alguns segundos de atraso.</p>
      } @else {
        <div class="cartao sem-padding tabela-rolagem">
          <table class="tabela">
            <thead><tr><th scope="col">Quando</th><th scope="col">Quem</th><th scope="col">O quê</th><th scope="col">Detalhe</th></tr></thead>
            <tbody>
              @for (e of filtrados(); track e.event_id) {
                <tr>
                  <td class="mono quando">{{ dataHora(e.ocorrido_em) }}</td>
                  <td><strong>{{ nomeDe(e.ator_id) }}</strong>@if (e.ator_papel) { <span class="papel"> · {{ papel(e.ator_papel) }}</span> }</td>
                  <td>{{ rotulo(e) }}<span class="mono tipo">{{ e.tipo }}</span></td>
                  <td class="detalhe">{{ detalhe(e) }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
      <p class="ajuda">Os eventos não podem ser editados nem apagados, nem pelo dono.</p>
    </section>
  `,
  styles: `
    .historico { display: flex; flex-direction: column; gap: 16px; }
    .barra { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; }
    .filtro { display: flex; gap: 10px; align-items: center; }
    .filtro .entrada { min-height: 44px; width: auto; padding: 0 12px; }
    .sem-padding { padding: 0; }
    .tabela { min-width: 680px; }
    .quando { font-size: 13px; white-space: nowrap; }
    .papel, .detalhe { color: var(--tinta-2); }
    .tipo { display: block; font-size: 12px; color: var(--tinta-3); }
  `,
})
export class HistoricoDaObraComponent implements OnInit {
  readonly obraId = input.required<string>();
  readonly equipe = input.required<MembroDaEquipeOut[]>();

  private auth = inject(AuthService);
  private servico = inject(ObrasService);

  readonly categorias = CATEGORIAS;
  readonly dataHora = dataHora;
  eventos = signal<EventoDoHistoricoOut[] | null>(null);
  erro = signal<ErroDaApi | null>(null);
  categoria = signal('');
  readonly filtrados = computed(() => {
    const c = this.categoria();
    const todos = this.eventos() ?? [];
    if (!c) return todos;
    return todos.filter((e) => (c === 'membro' ? (e.tipo ?? '').includes('membro') : (e.tipo ?? '').startsWith(c + '.') && !(e.tipo ?? '').includes('membro')));
  });

  ngOnInit(): void {
    this.servico
      .historico(this.obraId(), 100)
      .then((e) => this.eventos.set(e))
      .catch((e) => this.erro.set(paraErroDaApi(e)));
  }

  rotulo(e: EventoDoHistoricoOut): string {
    return EVENTOS[e.tipo ?? ''] ?? 'Evento';
  }

  papel(p: string): string {
    return (PAPEL[p] ?? p).toLowerCase();
  }

  nomeDe(id: number | null | undefined): string {
    if (id == null) return 'Sistema';
    if (id === this.auth.usuarioId()) return 'Você';
    return this.equipe().find((p) => p.usuario_id === id)?.nome ?? `Pessoa nº ${id}`;
  }

  /** O motivo da revisão, a situação nova da obra ou a pessoa adicionada, quando o evento traz. */
  detalhe(e: EventoDoHistoricoOut): string {
    const d = (e.dados ?? {}) as Record<string, unknown>;
    if (typeof d['motivo'] === 'string') return `Motivo: ${d['motivo']}`;
    if (typeof d['status'] === 'string') return `Agora: ${d['status']}`;
    if (typeof d['usuario_id'] === 'number' && (e.tipo ?? '').includes('membro')) {
      const papel = typeof d['papel'] === 'string' ? ` como ${this.papel(d['papel'])}` : '';
      return `${this.nomeDe(d['usuario_id'])}${papel}`;
    }
    if (typeof d['data'] === 'string') return `Diário de ${d['data'].split('-').reverse().join('/')}`;
    return '';
  }
}
