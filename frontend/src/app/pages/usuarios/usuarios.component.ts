import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import {
  UsuariosService,
  UsuarioAdmin,
  Papel,
  Permissao,
} from '../../services/usuarios.service';

interface Confirmacao {
  titulo: string;
  mensagem: string;
  botao: string;
  perigo: boolean;
  acao: () => void;
  aoCancelar?: () => void;
}

interface EdicaoPermissoes {
  usuario: UsuarioAdmin;
  selecionadas: Set<string>;
}

const TIER_POR_PAPEL: Record<string, string> = {
  admin: 'tier-admin',
  dono: 'tier-dono',
  encarregado: 'tier-encarregado',
  cliente: 'tier-cliente',
};

@Component({
  selector: 'app-usuarios',
  imports: [RouterLink, FormsModule, DatePipe],
  templateUrl: './usuarios.component.html',
  styleUrl: './usuarios.component.css',
})
export class UsuariosComponent implements OnInit {
  auth = inject(AuthService);
  private usuariosService = inject(UsuariosService);

  usuarios = signal<UsuarioAdmin[]>([]);
  papeis = signal<Papel[]>([]);
  permissoes = signal<Permissao[]>([]);
  carregando = signal(true);
  erro = signal('');
  aviso = signal('');
  salvandoId = signal<number | null>(null);

  busca = signal('');
  filtroPlano = signal<string | null>(null);

  confirmacao = signal<Confirmacao | null>(null);
  edicao = signal<EdicaoPermissoes | null>(null);

  private permissoesPorPlano = computed(() => {
    const mapa = new Map<string, Set<string>>();
    for (const p of this.papeis()) {
      mapa.set(p.slug, new Set(p.permissoes.map((perm) => perm.slug)));
    }
    return mapa;
  });

  contagemPorPlano = computed(() =>
    this.papeis().map((p) => ({
      papel: p,
      total: this.usuarios().filter((u) => u.role === p.slug).length,
    }))
  );

  usuariosFiltrados = computed(() => {
    const termo = this.busca().trim().toLowerCase();
    const plano = this.filtroPlano();
    return this.usuarios().filter(
      (u) =>
        (!plano || u.role === plano) &&
        (!termo || u.nome.toLowerCase().includes(termo) || u.email.toLowerCase().includes(termo))
    );
  });

  ngOnInit() {
    this.carregar();
  }

  carregar() {
    this.carregando.set(true);
    this.erro.set('');
    forkJoin({
      usuarios: this.usuariosService.listar(),
      papeis: this.usuariosService.listarPapeis(),
      permissoes: this.usuariosService.listarPermissoes(),
    }).subscribe({
      next: ({ usuarios, papeis, permissoes }) => {
        this.usuarios.set(usuarios);
        this.papeis.set(papeis);
        this.permissoes.set([...permissoes].sort((a, b) => a.id - b.id));
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

  tier(slug: string): string {
    return TIER_POR_PAPEL[slug] || 'tier-cliente';
  }

  nomePlano(slug: string): string {
    return this.papeis().find((p) => p.slug === slug)?.name || slug;
  }

  iniciais(nome: string): string {
    const partes = nome.trim().split(/\s+/);
    return ((partes[0]?.[0] || '') + (partes.length > 1 ? partes[partes.length - 1][0] : '')).toUpperCase();
  }

  /** Diferença entre as permissões efetivas do usuário e as do plano dele. */
  ajustes(u: UsuarioAdmin): { extras: number; removidas: number } {
    const doPlano = this.permissoesPorPlano().get(u.role) || new Set<string>();
    const efetivas = new Set(u.permissions);
    return {
      extras: u.permissions.filter((p) => !doPlano.has(p)).length,
      removidas: [...doPlano].filter((p) => !efetivas.has(p)).length,
    };
  }

  alternarFiltro(slug: string) {
    this.filtroPlano.update((atual) => (atual === slug ? null : slug));
  }

  // ---- Plano ----

  trocarPlano(u: UsuarioAdmin, select: HTMLSelectElement) {
    const novo = select.value;
    if (novo === u.role) return;

    const { extras, removidas } = this.ajustes(u);
    const aplicar = () => this.salvarPlano(u, novo, select);

    if (novo === 'admin' || extras + removidas > 0) {
      const partes: string[] = [];
      if (novo === 'admin') {
        partes.push(`${u.nome} passará a ter controle total do sistema, incluindo a gestão de usuários.`);
      }
      if (extras + removidas > 0) {
        partes.push('As permissões personalizadas deste usuário serão descartadas e ele passará a usar as permissões padrão do novo plano.');
      }
      this.confirmacao.set({
        titulo: `Mudar para ${this.nomePlano(novo)}?`,
        mensagem: partes.join(' '),
        botao: 'Mudar plano',
        perigo: novo === 'admin',
        acao: aplicar,
        aoCancelar: () => (select.value = u.role),
      });
    } else {
      aplicar();
    }
  }

  private salvarPlano(u: UsuarioAdmin, role: string, select: HTMLSelectElement) {
    this.salvandoId.set(u.id);
    this.erro.set('');
    this.usuariosService.alterarPlano(u.id, role).subscribe({
      next: (atualizado) => {
        this.substituir(atualizado);
        this.salvandoId.set(null);
        this.mostrarAviso(`${u.nome} agora está no plano ${this.nomePlano(atualizado.role)}.`);
      },
      error: (err) => {
        select.value = u.role;
        this.salvandoId.set(null);
        this.erro.set(err?.error?.detail || 'Não foi possível alterar o plano.');
      },
    });
  }

  // ---- Permissões ----

  abrirPermissoes(u: UsuarioAdmin) {
    this.edicao.set({ usuario: u, selecionadas: new Set(u.permissions) });
  }

  fecharPermissoes() {
    this.edicao.set(null);
  }

  alternarPermissao(slug: string) {
    const atual = this.edicao();
    if (!atual) return;
    const selecionadas = new Set(atual.selecionadas);
    selecionadas.has(slug) ? selecionadas.delete(slug) : selecionadas.add(slug);
    this.edicao.set({ ...atual, selecionadas });
  }

  restaurarPadrao() {
    const atual = this.edicao();
    if (!atual) return;
    const doPlano = this.permissoesPorPlano().get(atual.usuario.role) || new Set<string>();
    this.edicao.set({ ...atual, selecionadas: new Set(doPlano) });
  }

  origem(slug: string): 'plano' | 'extra' | 'removida' | null {
    const atual = this.edicao();
    if (!atual) return null;
    const noPlano = this.permissoesPorPlano().get(atual.usuario.role)?.has(slug) ?? false;
    const marcada = atual.selecionadas.has(slug);
    if (noPlano && marcada) return 'plano';
    if (!noPlano && marcada) return 'extra';
    if (noPlano && !marcada) return 'removida';
    return null;
  }

  edicaoAlterada = computed(() => {
    const atual = this.edicao();
    if (!atual) return false;
    const originais = new Set(atual.usuario.permissions);
    return (
      originais.size !== atual.selecionadas.size ||
      [...atual.selecionadas].some((p) => !originais.has(p))
    );
  });

  salvarPermissoes() {
    const atual = this.edicao();
    if (!atual) return;
    const u = atual.usuario;
    this.salvandoId.set(u.id);
    this.erro.set('');
    this.usuariosService.alterarPermissoes(u.id, [...atual.selecionadas]).subscribe({
      next: (atualizado) => {
        this.substituir(atualizado);
        this.salvandoId.set(null);
        this.edicao.set(null);
        this.mostrarAviso(`Permissões de ${u.nome} atualizadas.`);
      },
      error: (err) => {
        this.salvandoId.set(null);
        this.erro.set(err?.error?.detail || 'Não foi possível salvar as permissões.');
        this.edicao.set(null);
      },
    });
  }

  // ---- Remoção ----

  confirmarRemocao(u: UsuarioAdmin) {
    this.confirmacao.set({
      titulo: `Remover ${u.nome}?`,
      mensagem: `A conta ${u.email} será apagada junto com o perfil e a foto dela. Essa ação não pode ser desfeita.`,
      botao: 'Remover usuário',
      perigo: true,
      acao: () => this.remover(u),
    });
  }

  private remover(u: UsuarioAdmin) {
    this.salvandoId.set(u.id);
    this.erro.set('');
    this.usuariosService.remover(u.id).subscribe({
      next: () => {
        this.usuarios.update((lista) => lista.filter((x) => x.id !== u.id));
        this.salvandoId.set(null);
        this.mostrarAviso(`${u.nome} foi removido.`);
      },
      error: (err) => {
        this.salvandoId.set(null);
        this.erro.set(err?.error?.detail || 'Não foi possível remover o usuário.');
      },
    });
  }

  // ---- Diálogo de confirmação ----

  confirmar() {
    const c = this.confirmacao();
    this.confirmacao.set(null);
    c?.acao();
  }

  cancelarConfirmacao() {
    const c = this.confirmacao();
    this.confirmacao.set(null);
    c?.aoCancelar?.();
  }

  private substituir(atualizado: UsuarioAdmin) {
    this.usuarios.update((lista) =>
      lista.map((x) => (x.id === atualizado.id ? { ...x, ...atualizado } : x))
    );
  }

  private avisoTimer?: ReturnType<typeof setTimeout>;

  private mostrarAviso(msg: string) {
    this.aviso.set(msg);
    clearTimeout(this.avisoTimer);
    this.avisoTimer = setTimeout(() => this.aviso.set(''), 4000);
  }
}
