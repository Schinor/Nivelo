import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/auth.service';
import { mensagemDe } from '../../core/http/erro-da-api';

/** Quem entrou sem empresa (token sem tenant) cria a primeira aqui e vira dono. */
@Component({
  selector: 'app-criar-empresa',
  imports: [FormsModule],
  template: `
    <div class="cartao">
      <h2>Crie sua empresa</h2>
      <p class="sub">Você ainda não faz parte de nenhuma empresa. Crie a sua para registrar obras e diários.</p>
      <form class="formulario" (ngSubmit)="criar()">
        <div class="campo">
          <label for="nova-empresa">Nome da sua empresa ou seu nome profissional</label>
          <input id="nova-empresa" name="nome" [(ngModel)]="nome" required maxlength="120" [disabled]="enviando()" />
        </div>
        <div class="opcoes" role="radiogroup" aria-label="Tipo">
          <label class="opcao"><input type="radio" name="tipo" value="PF" [(ngModel)]="tipoPessoa" /><span>Autônomo (CPF)</span></label>
          <label class="opcao"><input type="radio" name="tipo" value="PJ" [(ngModel)]="tipoPessoa" /><span>Empresa (CNPJ)</span></label>
        </div>
        @if (erro()) { <p class="alerta alerta-erro" role="alert">{{ erro() }}</p> }
        <button type="submit" class="btn btn-primario btn-bloco" [disabled]="enviando() || nome.trim().length < 2">
          {{ enviando() ? 'Criando…' : 'Criar empresa' }}
        </button>
      </form>
    </div>
  `,
  styles: `.sub { color: var(--ink-muted); margin: 6px 0 16px; } h2 { margin-top: 0 !important; }`,
})
export class CriarEmpresaComponent {
  private auth = inject(AuthService);
  nome = '';
  tipoPessoa: 'PF' | 'PJ' = 'PF';
  enviando = signal(false);
  erro = signal<string | null>(null);

  criar(): void {
    this.enviando.set(true);
    this.erro.set(null);
    this.auth.criarEmpresa({ nome: this.nome.trim(), tipo_pessoa: this.tipoPessoa, documento: null }).subscribe({
      next: () => this.enviando.set(false),
      error: (e) => {
        this.erro.set(mensagemDe(e));
        this.enviando.set(false);
      },
    });
  }
}
