import { Component, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ObraResumoOut } from '../../api/models/obra-resumo-out';
import { AuthService } from '../../core/auth.service';
import { mensagemDe } from '../../core/http/erro-da-api';
import { data, plural, STATUS_DA_OBRA } from '../../shared/formatos';
import { CriarEmpresaComponent } from '../conta/criar-empresa.component';
import { ObrasService, StatusObra } from './obras.service';

/** Obras em cartões. Dono vê todas da empresa; encarregado e cliente, as que são membros. */
@Component({
  selector: 'app-lista-de-obras',
  imports: [RouterLink, CriarEmpresaComponent],
  template: `
    <main class="pagina">
      @if (auth.semEmpresa()) {
        <app-criar-empresa />
      } @else if (auth.isAdmin()) {
        <h1>Admin da plataforma</h1>
        <p class="sub">O admin não lê dados de obras, por privacidade dos clientes. Use o menu Usuários.</p>
      } @else {
        <header class="cabecalho">
          <div>
            <h1>Obras</h1>
            <p class="sub">{{ auth.contexto()?.empresa_nome }} · {{ total() === null ? '…' : plural(total()!, 'obra', 'obras') }}</p>
          </div>
          @if (auth.ehDono()) {
            <a class="btn btn-primario" routerLink="/obras/nova">+ Nova obra</a>
          }
        </header>

        <div class="opcoes filtros" role="radiogroup" aria-label="Filtrar por status">
          @for (f of filtros; track f.valor) {
            <label class="opcao">
              <input type="radio" name="filtro" [checked]="status() === f.valor" (change)="status.set(f.valor)" />
              <span>{{ f.rotulo }}</span>
            </label>
          }
        </div>

        @if (erro()) {
          <p class="alerta alerta-erro" role="alert">{{ erro() }}</p>
        } @else if (obras() === null) {
          <p class="carregando">Carregando obras…</p>
        } @else if (obras()!.length === 0) {
          <div class="vazio">
            @if (auth.ehDono()) {
              <p>{{ status() ? 'Nenhuma obra com esse status.' : 'Você ainda não cadastrou nenhuma obra.' }}</p>
              @if (!status()) { <a class="btn btn-primario" routerLink="/obras/nova">Cadastrar a primeira obra</a> }
            } @else {
              <p>Você ainda não foi incluído em nenhuma obra. Peça ao responsável para adicionar você.</p>
            }
          </div>
        } @else {
          <div class="lista">
            @for (o of obras(); track o.id) {
              <a class="cartao obra" [routerLink]="['/obras', o.id]">
                <div class="topo">
                  <h3>{{ o.nome }}</h3>
                  <span class="selo" [class]="'selo selo-' + o.status">{{ STATUS[o.status] }}</span>
                </div>
                <div class="meta">
                  <span>📍 {{ o.cidade }}/{{ o.uf }}</span>
                  <span>👤 {{ o.cliente_nome }}</span>
                  <span>🏁 Previsão {{ data(o.previsao_termino) }}</span>
                </div>
              </a>
            }
          </div>
          @if (temMais()) {
            <div class="acoes"><button class="btn btn-bloco" (click)="carregarMais()" [disabled]="carregando()">Carregar mais</button></div>
          }
        }
      }
    </main>
  `,
  styles: `
    .sub { color: var(--ink-muted); }
    .filtros { margin-bottom: var(--space-4); }
    .obra .topo { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); margin-bottom: var(--space-2); }
    .obra h3 { font-size: 1.1rem; line-height: 1.3; }
  `,
})
export class ListaDeObrasComponent {
  auth = inject(AuthService);
  private servico = inject(ObrasService);

  readonly STATUS = STATUS_DA_OBRA;
  readonly data = data;
  readonly plural = plural;
  readonly filtros: { valor: StatusObra | null; rotulo: string }[] = [
    { valor: null, rotulo: 'Todas' },
    { valor: 'ativa', rotulo: 'Ativas' },
    { valor: 'pausada', rotulo: 'Pausadas' },
    { valor: 'concluida', rotulo: 'Concluídas' },
  ];

  status = signal<StatusObra | null>(null);
  obras = signal<ObraResumoOut[] | null>(null);
  total = signal<number | null>(null);
  pagina = signal(1);
  carregando = signal(false);
  erro = signal<string | null>(null);
  temMais = computed(() => (this.obras()?.length ?? 0) < (this.total() ?? 0));

  constructor() {
    // Recarrega ao trocar o filtro ou a empresa ativa
    effect(() => {
      const status = this.status();
      if (this.auth.papel()) void this.carregar(status, 1);
    });
  }

  private async carregar(status: StatusObra | null, pagina: number): Promise<void> {
    this.carregando.set(true);
    this.erro.set(null);
    try {
      const r = await this.servico.listar(status, pagina);
      this.obras.set(pagina === 1 ? r.itens : [...(this.obras() ?? []), ...r.itens]);
      this.total.set(r.total);
      this.pagina.set(pagina);
    } catch (e) {
      this.erro.set(mensagemDe(e));
    } finally {
      this.carregando.set(false);
    }
  }

  carregarMais(): void {
    void this.carregar(this.status(), this.pagina() + 1);
  }
}
