import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { mensagemDe } from '../../core/http/erro-da-api';

/**
 * Cria uma empresa com quem está logado como dono. Aparece para quem entrou sem empresa (token
 * sem tenant) e em /empresas/nova ("Criar outra empresa"). O token devolvido já vem com ela ativa.
 */
@Component({
  selector: 'app-criar-empresa',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule],
  template: `
    <div class="pagina pagina-estreita">
      <header class="cabecalho">
        <div>
          <h1>Criar empresa</h1>
          <p class="sub">
            {{ auth.contexto() ? 'A nova empresa tem obras, equipe e assinatura próprias. Você entra nela como dono.'
               : 'Você ainda não faz parte de nenhuma empresa. Crie a sua para registrar obras e diários.' }}
          </p>
        </div>
      </header>
      <form class="cartao cartao-g formulario" (ngSubmit)="criar()" #f="ngForm">
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
        <div class="campo">
          <label for="nova-empresa">{{ tipoPessoa === 'PJ' ? 'Nome da empresa' : 'Nome profissional' }}</label>
          <input id="nova-empresa" name="nome" [(ngModel)]="nome" required minlength="2" maxlength="120" autocomplete="organization"
                 [placeholder]="tipoPessoa === 'PJ' ? 'Ex.: Alves Construções' : 'Ex.: João Pereira Reformas'" [disabled]="enviando()" />
        </div>
        <div class="campo">
          <label for="documento">{{ tipoPessoa === 'PJ' ? 'CNPJ' : 'CPF' }} <span class="opcional">(opcional)</span></label>
          <input id="documento" name="documento" inputmode="numeric" [(ngModel)]="documento" maxlength="20" [disabled]="enviando()"
                 [placeholder]="tipoPessoa === 'PJ' ? '00.000.000/0000-00' : '000.000.000-00'" />
        </div>
        @if (erro()) { <p class="alerta alerta-erro" role="alert">{{ erro() }}</p> }
        <button type="submit" class="btn btn-primario btn-grande btn-bloco" [disabled]="enviando() || f.invalid">
          {{ enviando() ? 'Criando…' : 'Criar empresa' }}
        </button>
      </form>
    </div>
  `,
})
export class CriarEmpresaComponent {
  auth = inject(AuthService);
  private router = inject(Router);

  nome = '';
  documento = '';
  tipoPessoa: 'PF' | 'PJ' = 'PJ';
  enviando = signal(false);
  erro = signal<string | null>(null);

  criar(): void {
    this.enviando.set(true);
    this.erro.set(null);
    this.auth
      .criarEmpresa({ nome: this.nome.trim(), tipo_pessoa: this.tipoPessoa, documento: this.documento.trim() || null })
      .subscribe({
        next: () => {
          this.enviando.set(false);
          void this.router.navigate(['/obras']);
        },
        error: (e) => {
          this.erro.set(mensagemDe(e));
          this.enviando.set(false);
        },
      });
  }
}
