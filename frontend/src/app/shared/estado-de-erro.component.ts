import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { ErroDaApi } from '../core/http/erro-da-api';
import { IconeComponent } from './icone.component';
import { PAPEL } from './formatos';

/**
 * Tela de erro do design: 404 (não existe ou é de outra empresa: a mesma resposta, sem revelar),
 * 403 (o papel não permite) e o genérico (500 ou sem conexão), com o código para o suporte.
 */
@Component({
  selector: 'app-estado-de-erro',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, IconeComponent],
  template: `
    <div class="vazio" [attr.role]="'alert'">
      @switch (tipo()) {
        @case ('404') {
          <span class="codigo">404</span>
          <h2>{{ recurso() }} não encontrad{{ genero() }}</h2>
          <p>Est{{ genero() === 'a' ? 'a' : 'e' }} {{ recurso().toLowerCase() }} não existe ou foi removid{{ genero() }}. Se recebeu o link de alguém, peça um convite novo.</p>
          <a routerLink="/obras" class="btn btn-contorno">Voltar para as obras</a>
        }
        @case ('403') {
          <span class="icone"><app-icone nome="cadeado" [tamanho]="26" /></span>
          <h2>Você não tem permissão para isso</h2>
          <p>
            @if (papel(); as p) { O seu papel nesta empresa é <strong>{{ p }}</strong>. }
            {{ erro().mensagem }}
          </p>
          <a routerLink="/obras" class="btn btn-contorno">Voltar para as obras</a>
        }
        @default {
          <span class="icone ambar"><app-icone nome="alerta" [tamanho]="26" /></span>
          <h2>{{ erro().status === 0 ? 'Sem conexão com o servidor' : 'Algo deu errado do nosso lado' }}</h2>
          <p>Nada do que você salvou foi perdido. Tente de novo em alguns segundos.</p>
          <button type="button" class="btn btn-primario" (click)="tentarDeNovo.emit()">Tentar de novo</button>
          @if (erro().problema.request_id) {
            <span class="pequeno mono">Código para o suporte: {{ erro().problema.request_id }}</span>
          }
        }
      }
    </div>
  `,
})
export class EstadoDeErroComponent {
  readonly erro = input.required<ErroDaApi>();
  /** "Obra", "Diário"... para o título do 404 */
  readonly recurso = input('Página');
  readonly genero = input<'a' | 'o'>('a');
  readonly tentarDeNovo = output<void>();

  private auth = inject(AuthService);
  readonly tipo = computed(() => (this.erro().status === 404 ? '404' : this.erro().status === 403 ? '403' : 'erro'));
  readonly papel = computed(() => {
    const p = this.auth.papel();
    return p ? PAPEL[p].toLowerCase() : null;
  });
}
