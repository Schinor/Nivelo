import { Component, OnInit, signal, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth.service';
import { paraErroDaApi } from '../../../core/http/erro-da-api';

@Component({
  selector: 'app-reset-password',
  imports: [FormsModule, RouterLink],
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.css',
})
export class ResetPasswordComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
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
      next: (res) => {
        this.carregando.set(false);
        this.sucesso.set(res.message || 'Senha alterada com sucesso! Redirecionando para login...');
        setTimeout(() => {
          this.router.navigate(['/login']);
        }, 2500);
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
