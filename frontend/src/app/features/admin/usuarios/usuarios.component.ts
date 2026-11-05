import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth.service';
import { UsuarioAdmin, UsuariosService } from './usuarios.service';

/** Contas da plataforma, para o admin. Papéis de negócio ficam nos vínculos de cada empresa. */
@Component({
  selector: 'app-usuarios',
  imports: [FormsModule, DatePipe],
  template: `
    <div class="pagina">
      <header class="cabecalho">
        <div>
          <span class="sobretitulo">Admin da plataforma</span>
          <h1>Contas</h1>
          <p class="sub">Os papéis de cada pessoa ficam nos vínculos com as empresas, não aqui. O admin não lê dados de obras.</p>
        </div>
      </header>

      @if (aviso()) { <p class="alerta alerta-sucesso" role="status">{{ aviso() }}</p> }
      @if (erro()) { <p class="alerta alerta-erro" role="alert">{{ erro() }}</p> }

      <section class="cartao cartao-g">
        <div class="cartao-titulo">
          <h2>Usuários <span class="mono contagem">{{ filtrados().length }}</span></h2>
          <div class="campo busca">
            <label for="busca" class="sr-only">Buscar usuários</label>
            <input id="busca" type="search" placeholder="Buscar por nome ou e-mail" [ngModel]="busca()" (ngModelChange)="busca.set($event)" />
          </div>
        </div>
        @if (carregando()) {
          <p class="carregando">Carregando…</p>
        } @else {
          <div class="tabela-rolagem">
            <table class="tabela">
              <thead><tr><th scope="col">Nome</th><th scope="col">E-mail</th><th scope="col">Desde</th><th scope="col"><span class="sr-only">Ações</span></th></tr></thead>
              <tbody>
                @for (u of filtrados(); track u.id) {
                  <tr>
                    <td><strong>{{ u.nome }}</strong> @if (u.admin) { <span class="selo selo-destaque">admin</span> }</td>
                    <td>{{ u.email }}</td>
                    <td class="mono">{{ u.criado_em | date: 'dd/MM/yyyy' }}</td>
                    <td class="direita">
                      @if (!ehVoce(u)) { <button type="button" class="btn btn-pequeno btn-perigo" (click)="pedirRemocao(u)">Remover</button> }
                      @else { <span class="ajuda">Você</span> }
                    </td>
                  </tr>
                } @empty {
                  <tr><td colspan="4" class="ajuda">Nenhuma conta encontrada.</td></tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>

    @if (aRemover(); as u) {
      <div class="fundo" (click)="cancelarRemocao()">
        <section class="modal" role="dialog" aria-modal="true" aria-labelledby="rem-t" (click)="$event.stopPropagation()">
          <h2 id="rem-t">Remover conta</h2>
          <p>A conta <strong>{{ u.email }}</strong> será apagada junto com os vínculos, o perfil e a foto. Essa ação não pode ser desfeita.</p>
          <div class="acoes acoes-direita">
            <button type="button" class="btn" (click)="cancelarRemocao()" [disabled]="removendo()">Cancelar</button>
            <button type="button" class="btn btn-perigo cheio" (click)="confirmarRemocao()" [disabled]="removendo()">
              {{ removendo() ? 'Removendo…' : 'Remover' }}
            </button>
          </div>
        </section>
      </div>
    }
  `,
  styles: `
    .busca { flex: 0 1 300px; }
    .contagem { font-size: 14px; color: var(--tinta-3); font-weight: 400; }
    .tabela { min-width: 600px; }
    .direita { text-align: right; }
    .fundo { position: fixed; inset: 0; z-index: 200; background: rgba(27, 30, 28, .55); display: flex; align-items: center; justify-content: center; padding: 24px; }
    .modal { width: 100%; max-width: 460px; background: var(--branco); border-radius: var(--raio-gg); padding: 28px; display: flex; flex-direction: column; gap: 16px; }
    .modal h2 { font-weight: 800; font-size: 24px; }
    .modal p { color: var(--tinta-2); }
  `,
})
export class UsuariosComponent implements OnInit {
  private usuariosService = inject(UsuariosService);
  auth = inject(AuthService);

  usuarios = signal<UsuarioAdmin[]>([]);
  carregando = signal(true);
  erro = signal<string | null>(null);
  aviso = signal<string | null>(null);
  busca = signal('');
  aRemover = signal<UsuarioAdmin | null>(null);
  removendo = signal(false);

  filtrados = computed(() => {
    const termo = this.busca().trim().toLowerCase();
    return this.usuarios().filter(
      (u) => !termo || u.nome.toLowerCase().includes(termo) || u.email.toLowerCase().includes(termo)
    );
  });

  ngOnInit() {
    this.usuariosService.listar().subscribe({
      next: (lista) => {
        this.usuarios.set(lista);
        this.carregando.set(false);
      },
      error: (err) => {
        this.erro.set(err?.error?.detail || 'Não foi possível carregar os usuários.');
        this.carregando.set(false);
      },
    });
  }

  ehVoce(u: UsuarioAdmin): boolean {
    return u.id === this.auth.user()?.id;
  }

  pedirRemocao(u: UsuarioAdmin) {
    this.aRemover.set(u);
  }

  cancelarRemocao() {
    this.aRemover.set(null);
  }

  confirmarRemocao() {
    const u = this.aRemover();
    if (!u) return;
    this.removendo.set(true);
    this.usuariosService.remover(u.id).subscribe({
      next: () => {
        this.usuarios.update((lista) => lista.filter((x) => x.id !== u.id));
        this.aviso.set(`A conta ${u.email} foi removida.`);
        this.removendo.set(false);
        this.aRemover.set(null);
      },
      error: (err) => {
        this.erro.set(err?.error?.detail || 'Não foi possível remover o usuário.');
        this.removendo.set(false);
        this.aRemover.set(null);
      },
    });
  }
}
