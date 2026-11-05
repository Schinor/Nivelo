import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth.service';
import { IconeComponent, NomeDoIcone } from '../../../shared/icone.component';
import { MarcaComponent } from '../../../shared/marca.component';
import { PLANOS } from '../../assinatura/planos';

/** Landing pública: a proposta de valor, como funciona, os recursos, os 3 planos e as dúvidas. */
@Component({
  selector: 'app-landing',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, IconeComponent, MarcaComponent],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent {
  auth = inject(AuthService);
  readonly planos = PLANOS;

  readonly dores = [
    { titulo: '“Isso não foi feito”', texto: 'Sem registro, a palavra do empreiteiro vale tanto quanto a do cliente. Com o diário, cada etapa tem data, foto e autor.' },
    { titulo: '“Como está a minha obra?”', texto: 'O cliente acompanha a obra pelo Nivelo e vê cada diário publicado. Menos ligação, mais confiança.' },
    { titulo: 'O caderno que molhou', texto: 'O histórico fica na nuvem e não se apaga: toda edição guarda o motivo e a versão anterior.' },
  ];

  readonly passos = [
    { titulo: 'Cadastre a obra', texto: 'Nome, endereço, cliente e previsão de entrega. Leva menos de um minuto.' },
    { titulo: 'Registre o dia', texto: 'O encarregado abre o celular, toca em “Registrar o dia de hoje”, tira as fotos e marca as atividades.' },
    { titulo: 'O cliente acompanha', texto: 'O cliente vê a linha do tempo da obra e comenta os diários publicados.' },
  ];

  readonly recursos: { icone: NomeDoIcone; titulo: string; texto: string; emBreve?: boolean }[] = [
    { icone: 'camera', titulo: 'Diário com fotos', texto: 'Fotos direto da câmera, comprimidas no próprio celular para enviar até com sinal fraco.' },
    { icone: 'alerta', titulo: 'Ocorrências', texto: 'Chuva, falta de material, pedido do cliente: tudo fica anotado no dia em que aconteceu.' },
    { icone: 'escudo', titulo: 'Histórico que não se apaga', texto: 'Cada revisão de diário exige um motivo e guarda a versão anterior. É o seu registro em caso de discussão.' },
    { icone: 'equipe', titulo: 'Equipe com papéis', texto: 'Dono, encarregado e cliente: cada um vê e faz só o que precisa. Convites por e-mail.' },
    { icone: 'link', titulo: 'Acesso do cliente', texto: 'O cliente acompanha sem pagar nada e nunca conta no limite do seu plano.' },
    { icone: 'documento', titulo: 'Relatório RDO em PDF', texto: 'O período da obra em um documento pronto para enviar ao cliente, com a marca da sua empresa.', emBreve: true },
  ];

  readonly duvidas = [
    { p: 'O meu cliente precisa pagar alguma coisa?', r: 'Não. O cliente entra pelo convite, acompanha a obra e comenta os diários sem custo, em qualquer plano.' },
    { p: 'Funciona no celular?', r: 'Sim. O Nivelo foi desenhado primeiro para o celular, com botões grandes e poucos campos, para usar no canteiro.' },
    { p: 'Posso cancelar quando quiser?', r: 'Sim. Ao cancelar, a empresa volta para o plano Free e o histórico continua guardado.' },
    { p: 'Sou autônomo, posso usar?', r: 'Pode. Na hora do cadastro, você escolhe entre empresa e autônomo. O funcionamento é o mesmo.' },
  ];

  readonly ano = new Date().getFullYear();
}
