import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { UsuarioAdmin, UsuariosService } from '../../services/usuarios.service';

/** Contas da plataforma, para o admin. Papéis de negócio ficam nos vínculos de cada empresa. */
@Component({
  selector: 'app-usuarios',
  imports: [RouterLink, FormsModule, DatePipe],
  templateUrl: './usuarios.component.html',
  styleUrl: './usuarios.component.css',
})
export class UsuariosComponent implements OnInit {
  private usuariosService = inject(UsuariosService);
  auth = inject(AuthService);

  usuarios = signal<UsuarioAdmin[]>([]);
  carregando = signal(true);
  erro = signal<string | null>(null);
  aviso = signal<string | null>(null);
  busca = signal('');
  aRemover = signal<UsuarioAdmin | null>(null);
  removendo = signal(false);

  filtrados = computed(() => {
    const termo = this.busca().trim().toLowerCase();
    return this.usuarios().filter(
      (u) => !termo || u.nome.toLowerCase().includes(termo) || u.email.toLowerCase().includes(termo)
    );
  });

  ngOnInit() {
    this.usuariosService.listar().subscribe({
      next: (lista) => {
        this.usuarios.set(lista);
        this.carregando.set(false);
      },
      error: (err) => {
        this.erro.set(err?.error?.detail || 'Não foi possível carregar os usuários.');
        this.carregando.set(false);
      },
    });
  }

  ehVoce(u: UsuarioAdmin): boolean {
    return u.id === this.auth.user()?.id;
  }

  pedirRemocao(u: UsuarioAdmin) {
    this.aRemover.set(u);
  }

  cancelarRemocao() {
    this.aRemover.set(null);
  }

  confirmarRemocao() {
    const u = this.aRemover();
    if (!u) return;
    this.removendo.set(true);
    this.usuariosService.remover(u.id).subscribe({
      next: () => {
        this.usuarios.update((lista) => lista.filter((x) => x.id !== u.id));
        this.aviso.set(`A conta ${u.email} foi removida.`);
        this.removendo.set(false);
        this.aRemover.set(null);
      },
      error: (err) => {
        this.erro.set(err?.error?.detail || 'Não foi possível remover o usuário.');
        this.removendo.set(false);
        this.aRemover.set(null);
      },
    });
  }
}
