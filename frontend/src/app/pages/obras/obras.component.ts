import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../services/auth.service';

/**
 * Tela provisória: a lista de obras e o diário chegam nas Fases 4 e 5.
 * Quem entra sem empresa (token sem tenant) cria a primeira aqui.
 */
@Component({
  selector: 'app-obras',
  standalone: true,
  imports: [FormsModule],
  template: `
    <main class="obras-page">
      @if (auth.semEmpresa()) {
        <h1>Crie sua empresa</h1>
        <p>Você ainda não faz parte de nenhuma empresa. Crie a sua para registrar obras e diários.</p>
        <form (ngSubmit)="criar()">
          <label for="nova-empresa">Nome da sua empresa ou seu nome profissional</label>
          <input id="nova-empresa" name="nome" [(ngModel)]="nome" required [disabled]="enviando()" />
          <div class="tipo">
            <label><input type="radio" name="tipo" value="PF" [(ngModel)]="tipoPessoa" /> Autônomo (CPF)</label>
            <label><input type="radio" name="tipo" value="PJ" [(ngModel)]="tipoPessoa" /> Empresa (CNPJ)</label>
          </div>
          @if (erro()) { <p class="erro" role="alert">{{ erro() }}</p> }
          <button type="submit" [disabled]="enviando() || !nome.trim()">
            {{ enviando() ? 'Criando…' : 'Criar empresa' }}
          </button>
        </form>
      } @else if (auth.isAdmin()) {
        <h1>Admin da plataforma</h1>
        <p>O admin não lê dados de obras. Use o menu Usuários.</p>
      } @else {
        <h1>Suas obras</h1>
        <p>Olá, {{ auth.user()?.nome }}. O cadastro de obras e o diário do dia estão chegando.</p>
      }
    </main>
  `,
  styles: `
    .obras-page { max-width: 720px; margin: 3rem auto; padding: 0 1.25rem; }
    h1 { margin-bottom: .75rem; }
    p { color: var(--text-muted, #9a9a9a); }
    form { display: grid; gap: .75rem; margin-top: 1.5rem; }
    input:not([type='radio']) { padding: .7rem .9rem; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-200); color: var(--ink); }
    .tipo { display: flex; gap: 1.25rem; }
    button { justify-self: start; padding: .75rem 1.2rem; border-radius: 6px; border: 0; background: var(--accent); color: var(--bg); font-weight: 700; }
    .erro { color: #e07a73; }
  `,
})
export class ObrasComponent {
  auth = inject(AuthService);

  nome = '';
  tipoPessoa: 'PF' | 'PJ' = 'PF';
  enviando = signal(false);
  erro = signal<string | null>(null);

  criar() {
    this.enviando.set(true);
    this.erro.set(null);
    this.auth.criarEmpresa({ nome: this.nome.trim(), tipo_pessoa: this.tipoPessoa, documento: null }).subscribe({
      next: () => this.enviando.set(false),
      error: (e) => {
        this.erro.set(typeof e?.error?.detail === 'string' ? e.error.detail : 'Não foi possível criar a empresa.');
        this.enviando.set(false);
      },
    });
  }
}
