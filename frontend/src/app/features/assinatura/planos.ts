/** Os planos do Nivelo (a fonte da verdade dos limites é a API: assinaturas/domain/planos.py). */
export interface PlanoDeVitrine {
  codigo: 'free' | 'pro' | 'construtora';
  nome: string;
  preco: string;
  destaque?: boolean;
  itens: string[];
}

export const PLANOS: PlanoDeVitrine[] = [
  {
    codigo: 'free',
    nome: 'Free',
    preco: 'R$ 0,00',
    itens: ['1 obra ativa', 'Diários ilimitados', '30 fotos por obra', 'Dono + 1 encarregado', 'Clientes acompanham de graça'],
  },
  {
    codigo: 'pro',
    nome: 'Pro',
    preco: 'R$ 29,90/mês',
    destaque: true,
    itens: ['Obras ativas ilimitadas', 'Fotos ilimitadas', 'Até 5 pessoas na equipe', 'Clientes ilimitados'],
  },
  {
    codigo: 'construtora',
    nome: 'Construtora',
    preco: 'R$ 69,90/mês',
    itens: ['Tudo do Pro', 'Equipe ilimitada', 'Logo da empresa no relatório'],
  },
];
