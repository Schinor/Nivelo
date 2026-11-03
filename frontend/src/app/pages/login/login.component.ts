import { Component, signal, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  auth = inject(AuthService);
  router = inject(Router);
  private route = inject(ActivatedRoute);

  modo = signal<'login' | 'cadastro' | 'esqueci-senha'>('login');
  carregando = signal(false);
  erro = signal('');
  sucesso = signal('');

  email = '';
  senha = '';
  nome = '';
  empresaNome = '';
  tipoPessoa: 'PF' | 'PJ' = 'PF';
  documento = '';
  emailRecuperacao = '';

  constructor() {
    if (this.route.snapshot.queryParamMap.get('cadastro') !== null) {
      this.modo.set('cadastro');
    }
  }

  mudarModo(novoModo: 'login' | 'cadastro' | 'esqueci-senha') {
    this.modo.set(novoModo);
    this.erro.set('');
    this.sucesso.set('');
  }

  entrar() {
    this.erro.set('');
    this.sucesso.set('');

    const emailTrimmed = this.email.trim();
    if (!emailTrimmed || !this.senha) {
      this.erro.set('Por favor, preencha todos os campos.');
      return;
    }

    this.carregando.set(true);
    this.auth.login(emailTrimmed, this.senha).subscribe({
      next: () => {
        this.carregando.set(false);
        this.router.navigate(['/obras']);
      },
      error: (e) => {
        this.carregando.set(false);
        this.erro.set(this.extrairErro(e, 'Erro ao fazer login. Verifique seu e-mail e senha.'));
      },
    });
  }

  registrar() {
    this.erro.set('');
    this.sucesso.set('');

    const nomeTrimmed = this.nome.trim();
    const emailTrimmed = this.email.trim();

    if (!nomeTrimmed || !emailTrimmed || !this.senha || !this.empresaNome.trim()) {
      this.erro.set('Por favor, preencha todos os campos.');
      return;
    }

    if (this.senha.length < 6) {
      this.erro.set('A senha deve ter pelo menos 6 caracteres.');
      return;
    }

    this.carregando.set(true);
    this.auth
      .cadastrar({
        nome: nomeTrimmed,
        email: emailTrimmed,
        senha: this.senha,
        empresa_nome: this.empresaNome.trim(),
        tipo_pessoa: this.tipoPessoa,
        documento: this.documento.trim() || null,
      })
      .subscribe({
      next: () => {
        this.carregando.set(false);
        this.sucesso.set('Conta criada com sucesso! Entrando...');
        this.auth.login(emailTrimmed, this.senha).subscribe({
          next: () => this.router.navigate(['/obras']),
          error: () => {
            this.modo.set('login');
            this.sucesso.set('Conta criada! Faça login com suas credenciais.');
          },
        });
      },
      error: (e) => {
        this.carregando.set(false);
        this.erro.set(this.extrairErro(e, 'Erro ao criar conta.'));
      },
    });
  }

  solicitarRecuperacao() {
    this.erro.set('');
    this.sucesso.set('');

    const emailTrimmed = this.emailRecuperacao.trim();
    if (!emailTrimmed) {
      this.erro.set('Por favor, informe seu e-mail.');
      return;
    }

    this.carregando.set(true);
    this.auth.esqueciSenha(emailTrimmed).subscribe({
      next: (res) => {
        this.carregando.set(false);
        this.sucesso.set(
          res.message || 'Se o e-mail estiver cadastrado, enviaremos um link de redefinição. Verifique sua caixa de entrada e o spam.'
        );
        this.emailRecuperacao = '';
      },
      error: (e) => {
        this.carregando.set(false);
        this.erro.set(this.extrairErro(e, 'Erro ao solicitar recuperação de senha.'));
      },
    });
  }

  private extrairErro(e: any, fallback: string): string {
    if (!e) return fallback;
    if (typeof e.error?.detail === 'string') {
      return e.error.detail;
    }
    if (Array.isArray(e.error?.detail) && e.error.detail.length > 0) {
      return e.error.detail
        .map((err: any) => err.msg || err.message || JSON.stringify(err))
        .join(', ');
    }
    if (typeof e.error?.message === 'string') {
      return e.error.message;
    }
    if (e.status === 0) {
      return 'Não foi possível conectar ao servidor. Tente novamente em instantes.';
    }
    return fallback;
  }
}
