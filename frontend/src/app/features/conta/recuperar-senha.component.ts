import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { mensagemDe } from '../../core/http/erro-da-api';
import { ESTILOS_DE_ACESSO } from './estilos-de-acesso';
import { TelaDeAcessoComponent } from './tela-de-acesso.component';

/** Pede o link de redefinição. A resposta é a mesma exista ou não o e-mail (não revela contas). */
@Component({
  selector: 'app-recuperar-senha',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, TelaDeAcessoComponent],
  template: `
    <app-tela-de-acesso frase="Esqueceu a senha? Acontece. O histórico das suas obras continua guardado.">
      @if (enviado()) {
        <div class="titulo">
          <h1>Confira o seu e-mail</h1>
          <p>Se <strong>{{ email }}</strong> tiver conta no Nivelo, você recebe um link para criar uma senha nova.
             O link vale por 30 minutos e só pode ser usado uma vez.</p>
        </div>
        <p class="alerta alerta-info">Não chegou? Veja a caixa de spam ou peça de novo em alguns minutos.</p>
        <a routerLink="/login" class="btn btn-contorno btn-grande btn-bloco">Voltar para entrar</a>
      } @else {
        <form class="formulario" (ngSubmit)="enviar()" #f="ngForm">
          <div class="titulo">
            <h1>Recuperar senha</h1>
            <p>Informe o e-mail da sua conta. Enviamos um link para você criar uma senha nova.</p>
          </div>
          <div class="campo">
            <label for="email">E-mail</label>
            <input id="email" name="email" type="email" inputmode="email" autocomplete="email" required
                   [(ngModel)]="email" [disabled]="enviando()" />
          </div>
          @if (erro()) { <p class="alerta alerta-erro" role="alert">{{ erro() }}</p> }
          <button type="submit" class="btn btn-primario btn-grande btn-bloco" [disabled]="enviando() || f.invalid">
            {{ enviando() ? 'Enviando…' : 'Enviar link' }}
          </button>
          <p class="rodape-form"><a routerLink="/login">Voltar para entrar</a></p>
        </form>
      }
    </app-tela-de-acesso>
  `,
  styles: ESTILOS_DE_ACESSO,
})
export class RecuperarSenhaComponent {
  private auth = inject(AuthService);
  email = '';
  enviando = signal(false);
  enviado = signal(false);
  erro = signal<string | null>(null);

  enviar(): void {
    this.enviando.set(true);
    this.erro.set(null);
    this.email = this.email.trim();
    this.auth.esqueciSenha(this.email).subscribe({
      next: () => {
        this.enviando.set(false);
        this.enviado.set(true);
      },
      error: (e) => {
        this.enviando.set(false);
        this.erro.set(mensagemDe(e));
      },
    });
  }
}
