import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';

interface Plano {
  nome: string;
  preco: string;
  destaque?: boolean;
  itens: string[];
}

/** Landing pública. Versão provisória da Fase 1; a definitiva vem na Fase 5. */
@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent {
  auth = inject(AuthService);

  readonly planos: Plano[] = [
    {
      nome: 'Free',
      preco: 'R$ 0,00',
      itens: ['1 obra ativa', 'Diários ilimitados', '30 fotos por obra', 'Dono + 1 encarregado', 'Clientes acompanham pelo app'],
    },
    {
      nome: 'Pro',
      preco: 'R$ 29,90/mês',
      destaque: true,
      itens: ['Obras ativas ilimitadas', 'Fotos ilimitadas', 'Até 5 pessoas na equipe', 'Clientes ilimitados'],
    },
    {
      nome: 'Construtora',
      preco: 'R$ 69,90/mês',
      itens: ['Tudo do Pro', 'Equipe ilimitada', 'Logo da empresa no relatório'],
    },
  ];

  irParaPlanos(): void {
    document.getElementById('planos')?.scrollIntoView({ behavior: 'smooth' });
  }
}
