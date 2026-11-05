import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { ESTILOS_DE_ACESSO } from './estilos-de-acesso';
import { TelaDeAcessoComponent } from './tela-de-acesso.component';

/**
 * Cadastro público, passo 1 de 2: cria a empresa (PJ) ou o autônomo (PF), a conta e o vínculo de
 * dono (o papel nunca vai no corpo). O passo 2 é cadastrar a primeira obra.
 */
@Component({
  selector: 'app-cadastro',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, TelaDeAcessoComponent],
  template: `
    <app-tela-de-acesso frase="Comece grátis, com a sua primeira obra." [largura]="480"
                        [itens]="['Diários ilimitados no plano Free', 'Sem cartão de crédito', 'Convide o cliente sem custo']">
      <form class="formulario" (ngSubmit)="criar()" #f="ngForm">
        <div class="titulo">
          <span class="passo">Passo 1 de 2 · Sua conta</span>
          <h1>Criar conta</h1>
        </div>

        <fieldset class="campo">
          <legend class="rotulo">Você trabalha como</legend>
          <div class="escolhas esquerda">
            <label class="escolha">
              <input type="radio" name="tipo" value="PJ" [(ngModel)]="tipoPessoa" />
              <span><strong>Empresa</strong><small>Construtora ou empreiteira</small></span>
            </label>
            <label class="escolha">
              <input type="radio" name="tipo" value="PF" [(ngModel)]="tipoPessoa" />
              <span><strong>Autônomo</strong><small>Trabalho por conta própria</small></span>
            </label>
          </div>
        </fieldset>

        <div class="campo" [class.invalido]="erro()?.campo('empresa_nome')">
          <label for="org">{{ tipoPessoa === 'PJ' ? 'Nome da empresa' : 'Nome profissional' }}</label>
          <input id="org" name="org" required maxlength="120" autocomplete="organization" [(ngModel)]="empresaNome"
                 [placeholder]="tipoPessoa === 'PJ' ? 'Ex.: Alves Construções' : 'Ex.: João Pereira Reformas'" />
          @if (erro()?.campo('empresa_nome'); as m) { <span class="erro-campo">{{ m }}</span> }
        </div>
        <div class="campo" [class.invalido]="erro()?.campo('nome')">
          <label for="nome">Seu nome</label>
          <input id="nome" name="nome" required maxlength="100" autocomplete="name" [(ngModel)]="nome" />
          @if (erro()?.campo('nome'); as m) { <span class="erro-campo">{{ m }}</span> }
        </div>
        <div class="campo" [class.invalido]="erro()?.campo('email')">
          <label for="email">E-mail</label>
          <input id="email" name="email" type="email" inputmode="email" required autocomplete="email" [(ngModel)]="email" />
          @if (erro()?.campo('email'); as m) { <span class="erro-campo">{{ m }}</span> }
        </div>
        <div class="campo" [class.invalido]="erro()?.campo('senha')">
          <label for="senha">Senha</label>
          <input id="senha" name="senha" type="password" required minlength="6" maxlength="72" autocomplete="new-password"
                 aria-describedby="senha-ajuda" [(ngModel)]="senha" />
          <span id="senha-ajuda" class="ajuda">Mínimo de 6 caracteres.</span>
        </div>

        @if (erro(); as e) { <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p> }

        <button type="submit" class="btn btn-primario btn-grande btn-bloco" [disabled]="enviando() || f.invalid">
          {{ enviando() ? 'Criando a conta…' : 'Criar conta e cadastrar a primeira obra' }}
        </button>
        <p class="rodape-form">Já tem conta? <a routerLink="/login">Entrar</a></p>
      </form>
    </app-tela-de-acesso>
  `,
  styles: ESTILOS_DE_ACESSO,
})
export class CadastroComponent {
  private auth = inject(AuthService);
  private router = inject(Router);

  tipoPessoa: 'PF' | 'PJ' = 'PJ';
  empresaNome = '';
  nome = '';
  email = '';
  senha = '';
  enviando = signal(false);
  erro = signal<ErroDaApi | null>(null);

  criar(): void {
    this.enviando.set(true);
    this.erro.set(null);
    const email = this.email.trim();
    this.auth
      .cadastrar({
        nome: this.nome.trim(),
        email,
        senha: this.senha,
        empresa_nome: this.empresaNome.trim(),
        tipo_pessoa: this.tipoPessoa,
        documento: null,
      })
      .subscribe({
        next: () =>
          this.auth.login(email, this.senha).subscribe({
            next: () => void this.router.navigate(['/obras/nova'], { state: { primeira: true } }),
            error: () => void this.router.navigate(['/login']),
          }),
        error: (e) => {
          this.erro.set(paraErroDaApi(e));
          this.enviando.set(false);
        },
      });
  }
}
