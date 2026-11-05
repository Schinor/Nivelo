import { Component, OnInit, signal, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth.service';
import { paraErroDaApi } from '../../../core/http/erro-da-api';
import { ESTILOS_DE_ACESSO } from '../estilos-de-acesso';
import { TelaDeAcessoComponent } from '../tela-de-acesso.component';

/** Link do e-mail (/reset-password?token=): confere o token e grava a senha nova. */
@Component({
  selector: 'app-reset-password',
  imports: [FormsModule, RouterLink, TelaDeAcessoComponent],
  template: `
    <app-tela-de-acesso frase="Crie uma senha nova e volte para as suas obras.">
      @if (verificando()) {
        <p class="carregando">Conferindo o link…</p>
      } @else if (!tokenValido()) {
        <div class="titulo">
          <h1>Link expirado</h1>
          <p>{{ erro() || 'Este link de redefinição não vale mais. Ele dura 30 minutos e só pode ser usado uma vez.' }}</p>
        </div>
        <a routerLink="/recuperar-senha" class="btn btn-primario btn-grande btn-bloco">Pedir um link novo</a>
        <p class="rodape-form"><a routerLink="/login">Voltar para entrar</a></p>
      } @else if (sucesso()) {
        <div class="titulo">
          <h1>Senha alterada</h1>
          <p>{{ sucesso() }}</p>
        </div>
        <a routerLink="/login" class="btn btn-primario btn-grande btn-bloco">Entrar</a>
      } @else {
        <form class="formulario" (ngSubmit)="redefinir()" #f="ngForm">
          <div class="titulo">
            <h1>Criar senha nova</h1>
            @if (emailUsuario()) { <p>Para a conta <strong>{{ emailUsuario() }}</strong>.</p> }
          </div>
          <div class="campo">
            <label for="nova">Senha nova</label>
            <input id="nova" name="nova" type="password" required minlength="6" maxlength="72" autocomplete="new-password"
                   aria-describedby="nova-ajuda" [(ngModel)]="novaSenha" [disabled]="carregando()" />
            <span id="nova-ajuda" class="ajuda">Mínimo de 6 caracteres.</span>
          </div>
          <div class="campo" [class.invalido]="confirmacaoSenha && confirmacaoSenha !== novaSenha">
            <label for="repetir">Repita a senha nova</label>
            <input id="repetir" name="repetir" type="password" required autocomplete="new-password"
                   [(ngModel)]="confirmacaoSenha" [disabled]="carregando()" />
            @if (confirmacaoSenha && confirmacaoSenha !== novaSenha) { <span class="erro-campo">As senhas não são iguais.</span> }
          </div>
          @if (erro()) { <p class="alerta alerta-erro" role="alert">{{ erro() }}</p> }
          <button type="submit" class="btn btn-primario btn-grande btn-bloco" [disabled]="carregando() || f.invalid">
            {{ carregando() ? 'Salvando…' : 'Salvar senha nova' }}
          </button>
        </form>
      }
    </app-tela-de-acesso>
  `,
  styles: ESTILOS_DE_ACESSO,
})
export class ResetPasswordComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private auth = inject(AuthService);

  token = signal<string>('');
  verificando = signal(true);
  tokenValido = signal(false);
  emailUsuario = signal<string | null>(null);

  novaSenha = '';
  confirmacaoSenha = '';
  carregando = signal(false);
  erro = signal('');
  sucesso = signal('');

  ngOnInit(): void {
    this.route.queryParams.subscribe((params) => {
      const tokenParam = params['token'];
      if (!tokenParam) {
        this.verificando.set(false);
        this.tokenValido.set(false);
        this.erro.set('Nenhum token de recuperação fornecido na URL.');
        return;
      }

      this.token.set(tokenParam);
      this.validarToken(tokenParam);
    });
  }

  validarToken(token: string): void {
    this.verificando.set(true);
    this.auth.validarTokenReset(token).subscribe({
      next: (res) => {
        this.verificando.set(false);
        this.tokenValido.set(res.valid);
        if (res.valid) {
          this.emailUsuario.set(res.email || null);
        } else {
          this.erro.set(res.message || 'Token inválido ou expirado.');
        }
      },
      error: () => {
        this.verificando.set(false);
        this.tokenValido.set(false);
        this.erro.set('Não foi possível validar o link de recuperação. Tente novamente.');
      },
    });
  }

  redefinir(): void {
    this.erro.set('');
    this.sucesso.set('');

    if (!this.novaSenha || !this.confirmacaoSenha) {
      this.erro.set('Por favor, preencha todos os campos.');
      return;
    }

    if (this.novaSenha.length < 6) {
      this.erro.set('A nova senha deve conter no mínimo 6 caracteres.');
      return;
    }

    if (this.novaSenha !== this.confirmacaoSenha) {
      this.erro.set('As senhas digitadas não coincidem.');
      return;
    }

    this.carregando.set(true);
    this.auth.redefinirSenha(this.token(), this.novaSenha).subscribe({
      next: () => {
        this.carregando.set(false);
        this.sucesso.set('Pronto. Entre com o seu e-mail e a senha nova.');
      },
      error: (e) => {
        this.carregando.set(false);
        this.erro.set(this.extrairErro(e, 'Erro ao redefinir a senha.'));
      },
    });
  }

  /** O interceptor já traduziu o Problem Details; sem `detail`, usa o texto da tela. */
  private extrairErro(e: unknown, fallback: string): string {
    const erro = paraErroDaApi(e);
    return (erro.problema.detail || erro.status === 0) ? erro.mensagem : fallback;
  }
}
