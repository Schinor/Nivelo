/** Os planos do Nivelo (a fonte da verdade dos limites é a API: assinaturas/domain/planos.py). */
export interface PlanoDeVitrine {
  codigo: 'free' | 'pro' | 'construtora';
  nome: string;
  /** Valor sem o "/mês", para o número grande do cartão */
  valor: string;
  descricao: string;
  /** Resumo de uma linha (modal do limite) */
  resumo: string;
  destaque?: boolean;
  itens: string[];
}

export const PLANOS: PlanoDeVitrine[] = [
  {
    codigo: 'free',
    nome: 'Free',
    valor: 'R$ 0',
    descricao: 'Para provar o valor na primeira obra',
    resumo: '1 obra ativa e 30 fotos por obra',
    itens: ['1 obra ativa', 'Diários ilimitados', '30 fotos por obra', '1 encarregado', 'Ocorrências e histórico de auditoria'],
  },
  {
    codigo: 'pro',
    nome: 'Pro',
    valor: 'R$ 29,90',
    descricao: 'Para quem toca várias obras',
    resumo: 'Obras e fotos ilimitadas, até 5 pessoas',
    destaque: true,
    itens: ['Obras ativas ilimitadas', 'Diários e fotos ilimitados', 'Até 5 pessoas na equipe', 'Tudo do Free'],
  },
  {
    codigo: 'construtora',
    nome: 'Construtora',
    valor: 'R$ 69,90',
    descricao: 'Para equipes maiores',
    resumo: 'Equipe ilimitada e logo no relatório',
    itens: ['Tudo do Pro', 'Equipe ilimitada', 'Logo da empresa no relatório'],
  },
];

export function plano(codigo: string | null | undefined): PlanoDeVitrine {
  return PLANOS.find((p) => p.codigo === codigo) ?? PLANOS[1];
}
