import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth.service';
import { PLANOS } from '../../assinatura/planos';

/** Landing pública: a proposta de valor do README, os 3 planos e "Criar conta grátis". */
@Component({
  selector: 'app-landing',
  imports: [RouterLink],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent {
  auth = inject(AuthService);
  readonly planos = PLANOS;

  readonly passos = [
    { icone: '📷', titulo: 'Fotografe o dia', texto: 'Tire as fotos pelo celular, no canteiro. O app reduz o tamanho antes de enviar.' },
    { icone: '📝', titulo: 'Registre em 2 minutos', texto: 'Clima, efetivo, o que foi feito e as ocorrências: chuva, falta de material, pedido do cliente.' },
    { icone: '✅', titulo: 'Publique para o cliente', texto: 'O cliente acompanha pelo app. Diário publicado não é sobrescrito: mudar exige motivo.' },
  ];

  readonly dores = [
    { titulo: 'Última parcela retida', texto: 'Sem registro do atraso por chuva, a discussão no fim da obra vira desconto.' },
    { titulo: 'Foto perdida no WhatsApp', texto: '“Eu tenho foto de tudo, o problema é achar.” No Nivelo cada foto fica no dia certo.' },
    { titulo: 'Cliente ligando toda hora', texto: 'Ele vê o diário publicado com data, autor e fotos, sem precisar perguntar.' },
  ];

  irParaPlanos(): void {
    document.getElementById('planos')?.scrollIntoView({ behavior: 'smooth' });
  }
}
