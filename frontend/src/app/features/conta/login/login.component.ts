import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth.service';
import { paraErroDaApi } from '../../../core/http/erro-da-api';
import { ESTILOS_DE_ACESSO } from '../estilos-de-acesso';
import { TelaDeAcessoComponent } from '../tela-de-acesso.component';

/** Entrar com e-mail e senha. Volta para a tela de onde a sessão expirou (?voltar=). */
@Component({
  selector: 'app-login',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, TelaDeAcessoComponent],
  template: `
    <app-tela-de-acesso frase="Bom te ver de novo. Hoje tem diário para registrar?"
                        [itens]="['O diário de hoje em poucos minutos', 'Fotos direto da câmera', 'O cliente acompanha sem ligar']">
      <form class="formulario" (ngSubmit)="entrar()" #f="ngForm">
        <div class="titulo">
          <h1>Entrar</h1>
          <p>Use o e-mail e a senha da sua conta.</p>
        </div>
        @if (erro()) { <p class="alerta alerta-erro" role="alert">{{ erro() }}</p> }
        <div class="campo">
          <label for="email">E-mail</label>
          <input id="email" name="email" type="email" inputmode="email" autocomplete="username" required
                 [(ngModel)]="email" [disabled]="carregando()" />
        </div>
        <div class="campo">
          <div class="linha-rotulo">
            <label for="senha" class="rotulo">Senha</label>
            <a routerLink="/recuperar-senha">Esqueci a senha</a>
          </div>
          <input id="senha" name="senha" type="password" autocomplete="current-password" required
                 [(ngModel)]="senha" [disabled]="carregando()" />
        </div>
        <button type="submit" class="btn btn-primario btn-grande btn-bloco" [disabled]="carregando() || f.invalid">
          {{ carregando() ? 'Entrando…' : 'Entrar' }}
        </button>
        <p class="rodape-form">Ainda não tem conta? <a routerLink="/cadastro">Criar conta grátis</a></p>
      </form>
    </app-tela-de-acesso>
  `,
  styles: ESTILOS_DE_ACESSO,
})
export class LoginComponent {
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  carregando = signal(false);
  erro = signal('');
  email = '';
  senha = '';

  entrar(): void {
    this.erro.set('');
    this.carregando.set(true);
    this.auth.login(this.email.trim(), this.senha).subscribe({
      next: () => {
        this.carregando.set(false);
        const voltar = this.route.snapshot.queryParamMap.get('voltar');
        // Só caminho interno: nunca redireciona para fora do app
        const destino = voltar && voltar.startsWith('/') && !voltar.startsWith('//') ? voltar : '/obras';
        void this.router.navigateByUrl(destino);
      },
      error: (e) => {
        this.carregando.set(false);
        const erro = paraErroDaApi(e);
        this.erro.set(erro.status === 401 && !erro.problema.detail ? 'E-mail ou senha incorretos.' : erro.mensagem);
      },
    });
  }
}
