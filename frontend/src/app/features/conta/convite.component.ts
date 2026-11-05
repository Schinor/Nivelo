import { Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { AvisosService } from '../../core/avisos.service';
import { ErroDaApi, paraErroDaApi } from '../../core/http/erro-da-api';
import { EquipeService } from './equipe.service';
import { ESTILOS_DE_ACESSO } from './estilos-de-acesso';
import { TelaDeAcessoComponent } from './tela-de-acesso.component';

/** Aceite do convite (link do e-mail: /convite?token=...). Quem já tem conta com o e-mail do
 * convite só confirma; quem não tem cria a senha aqui. */
@Component({
  selector: 'app-convite',
  imports: [FormsModule, RouterLink, TelaDeAcessoComponent],
  template: `
    <app-tela-de-acesso frase="Você foi convidado para acompanhar uma obra no Nivelo."
                        [itens]="['Diário do dia com fotos', 'Ocorrências registradas no dia em que aconteceram', 'Para o cliente, é grátis']">
      @if (!token()) {
        <div class="titulo">
          <h1>Link incompleto</h1>
          <p>O link do convite chegou cortado. Abra de novo o link do e-mail ou peça um convite novo a quem convidou você.</p>
        </div>
        <a routerLink="/" class="btn btn-contorno btn-grande btn-bloco">Conhecer o Nivelo</a>
      } @else if (aceito()) {
        <div class="titulo">
          <span class="selo selo-ativa feito">Convite aceito</span>
          <h1>Pronto, você está na equipe</h1>
          <p>{{ auth.isLoggedIn() ? 'Para ver a nova empresa, saia e entre de novo, ou troque de empresa em Minha conta.' : 'Entre com o seu e-mail e a senha para ver a obra.' }}</p>
        </div>
        <a class="btn btn-primario btn-grande btn-bloco" [routerLink]="auth.isLoggedIn() ? '/conta' : '/login'">{{ auth.isLoggedIn() ? 'Ir para Minha conta' : 'Entrar' }}</a>
      } @else {
        <form class="formulario" (ngSubmit)="aceitar()" #f="ngForm">
          <div class="titulo">
            <h1>Aceitar convite</h1>
            <p>Use o mesmo e-mail que recebeu o convite.</p>
          </div>
          <fieldset class="campo">
            <legend class="rotulo">Você já tem conta no Nivelo?</legend>
            <div class="escolhas">
              <label class="escolha"><input type="radio" name="conta" [value]="false" [(ngModel)]="jaTenhoConta" /><span>Ainda não</span></label>
              <label class="escolha"><input type="radio" name="conta" [value]="true" [(ngModel)]="jaTenhoConta" /><span>Já tenho</span></label>
            </div>
          </fieldset>
          @if (!jaTenhoConta) {
            <div class="campo">
              <label for="nome">Seu nome</label>
              <input id="nome" name="nome" [(ngModel)]="nome" required minlength="2" maxlength="100" autocomplete="name" />
            </div>
            <div class="campo">
              <label for="senha">Crie uma senha</label>
              <input id="senha" name="senha" type="password" [(ngModel)]="senha" required minlength="6" maxlength="72" autocomplete="new-password" aria-describedby="senha-ajuda" />
              <span id="senha-ajuda" class="ajuda">Mínimo de 6 caracteres. O e-mail é o do convite.</span>
            </div>
          } @else {
            <p class="alerta alerta-info">Você entra na empresa com a conta que já tem, no e-mail que recebeu o convite.</p>
          }
          @if (erro(); as e) { <p class="alerta alerta-erro" role="alert">{{ e.mensagem }}</p> }
          <button type="submit" class="btn btn-primario btn-grande btn-bloco" [disabled]="enviando() || f.invalid">
            {{ enviando() ? 'Confirmando…' : 'Aceitar convite' }}
          </button>
        </form>
      }
    </app-tela-de-acesso>
  `,
  styles: ESTILOS_DE_ACESSO + `.feito { align-self: flex-start; }`,
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
