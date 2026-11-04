import { Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { EquipeService } from './equipe.service';

/** Aceite do convite (link do e-mail: /convite?token=...). Quem já tem conta com o e-mail do
 * convite só confirma; quem não tem cria a senha aqui. */
@Component({
  selector: 'app-convite',
  imports: [FormsModule, RouterLink],
  template: `
    <main class="pagina estreita">
      <h1>Convite para o Nivelo</h1>
      @if (!token()) {
        <p class="alerta alerta-erro">Link de convite incompleto. Abra de novo o link do e-mail.</p>
      } @else if (aceito()) {
        <p class="alerta alerta-sucesso">Pronto! Você entrou na equipe. {{ auth.isLoggedIn() ? 'Troque para a nova empresa ao entrar de novo.' : 'Entre com seu e-mail e senha.' }}</p>
        <a class="btn btn-primario btn-bloco" [routerLink]="auth.isLoggedIn() ? '/obras' : '/login'">{{ auth.isLoggedIn() ? 'Ir para as obras' : 'Entrar' }}</a>
      } @else {
        <div class="opcoes" role="radiogroup" aria-label="Você já tem conta?">
          <label class="opcao"><input type="radio" name="conta" [value]="false" [(ngModel)]="jaTenhoConta" /><span>Criar minha conta</span></label>
          <label class="opcao"><input type="radio" name="conta" [value]="true" [(ngModel)]="jaTenhoConta" /><span>Já tenho conta</span></label>
        </div>
        <form class="formulario" (ngSubmit)="aceitar()" #f="ngForm">
          @if (!jaTenhoConta) {
            <div class="campo">
              <label for="nome">Seu nome</label>
              <input id="nome" name="nome" [(ngModel)]="nome" required minlength="2" maxlength="100" autocomplete="name" />
            </div>
            <div class="campo">
              <label for="senha">Crie uma senha</label>
              <input id="senha" name="senha" type="password" [(ngModel)]="senha" required minlength="6" maxlength="72" autocomplete="new-password" />
              <span class="ajuda">Pelo menos 6 caracteres. O e-mail é o do convite.</span>
            </div>
          } @else {
            <p class="ajuda">Você entra na empresa com a conta que já tem, no e-mail que recebeu o convite.</p>
          }
          @if (erro(); as e) { <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p> }
          <button type="submit" class="btn btn-primario btn-bloco" [disabled]="enviando() || f.invalid">
            {{ enviando() ? 'Confirmando…' : 'Aceitar convite' }}
          </button>
        </form>
      }
    </main>
  `,
  styles: `.estreita { max-width: 460px; } h1 { margin-bottom: var(--space-4); } .opcoes { margin-bottom: var(--space-4); } .ajuda { color: var(--ink-faint); font-size: .85rem; }`,
})
export class ConviteComponent {
  /** ?token= do link do e-mail */
  readonly token = input<string>();

  auth = inject(AuthService);
  private servico = inject(EquipeService);
  private avisos = inject(AvisosService);
  private router = inject(Router);

  jaTenhoConta = false;
  nome = '';
  senha = '';
  enviando = signal(false);
  aceito = signal(false);
  erro = signal<ErroDaApi | null>(null);

  async aceitar(): Promise<void> {
    this.enviando.set(true);
    this.erro.set(null);
    try {
      const r = await this.servico.aceitar(
        this.token()!,
        this.jaTenhoConta ? null : this.nome.trim(),
        this.jaTenhoConta ? null : this.senha,
      );
      this.aceito.set(true);
      if (r.novo_usuario) this.avisos.sucesso('Conta criada. Entre com seu e-mail e a senha que você escolheu.');
      if (!this.auth.isLoggedIn()) await this.router.navigate(['/login']);
    } catch (e) {
      this.erro.set(paraErroDaApi(e));
    } finally {
      this.enviando.set(false);
    }
  }
}
