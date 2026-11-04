import { Injectable, signal } from '@angular/core';
import { ProblemDetails } from './http/erro-da-api';

export interface Aviso {
  texto: string;
  tipo: 'sucesso' | 'erro' | 'info';
}

export interface Confirmacao {
  titulo: string;
  texto: string;
  confirmar: string;
  perigo: boolean;
  responder: (sim: boolean) => void;
}

/** Estado global de avisos: a mensagem rápida (toast), o pedido de confirmação e o modal do
 * limite do plano (402). Renderizado por `AvisosComponent`. */
@Injectable({ providedIn: 'root' })
export class AvisosService {
  readonly aviso = signal<Aviso | null>(null);
  readonly confirmacao = signal<Confirmacao | null>(null);
  readonly limiteDoPlano = signal<ProblemDetails | null>(null);
  private timer?: ReturnType<typeof setTimeout>;

  mostrar(texto: string, tipo: Aviso['tipo'] = 'info'): void {
    clearTimeout(this.timer);
    this.aviso.set({ texto, tipo });
    this.timer = setTimeout(() => this.aviso.set(null), tipo === 'erro' ? 6000 : 3500);
  }

  sucesso(texto: string): void {
    this.mostrar(texto, 'sucesso');
  }

  erro(texto: string): void {
    this.mostrar(texto, 'erro');
  }

  /** Pergunta antes de uma ação que não tem volta (ex.: remover). */
  confirmar(titulo: string, texto: string, opcoes: { confirmar?: string; perigo?: boolean } = {}): Promise<boolean> {
    return new Promise((resolver) => {
      this.confirmacao.set({
        titulo,
        texto,
        confirmar: opcoes.confirmar ?? 'Confirmar',
        perigo: opcoes.perigo ?? false,
        responder: (sim) => {
          this.confirmacao.set(null);
          resolver(sim);
        },
      });
    });
  }

  abrirLimiteDoPlano(problema: ProblemDetails): void {
    this.limiteDoPlano.set(problema);
  }

  fecharLimiteDoPlano(): void {
    this.limiteDoPlano.set(null);
  }
}
