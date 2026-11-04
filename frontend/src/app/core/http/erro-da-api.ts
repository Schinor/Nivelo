import { HttpErrorResponse } from '@angular/common/http';

/** Campos do Problem Details (RFC 9457) que a API devolve em todo erro. */
export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  request_id?: string;
  errors?: { campo: string; mensagem: string }[];
  // 402 do plano
  limite?: number;
  atual?: number;
  plano_atual?: string;
  plano_sugerido?: string | null;
  acao?: string;
  // 409 de versão
  versao_atual?: number;
  [extra: string]: unknown;
}

const BASE_TYPE = 'https://nivelo/erros/';

/**
 * Erro da API já traduzido: o front decide pelo `codigo` (o final do `type` estável), nunca
 * pelo texto. `mensagem` é o que se mostra para a pessoa.
 */
export class ErroDaApi extends Error {
  constructor(
    readonly status: number,
    readonly codigo: string,
    readonly mensagem: string,
    readonly problema: ProblemDetails,
  ) {
    super(mensagem);
    this.name = 'ErroDaApi';
  }

  /** Mensagem de um campo do formulário (422 de validação), se houver. */
  campo(nome: string): string | null {
    return this.problema.errors?.find((e) => e.campo === nome || e.campo.endsWith(`.${nome}`))?.mensagem ?? null;
  }
}

const MENSAGEM_POR_STATUS: Record<number, string> = {
  0: 'Sem conexão com o servidor. Confira a internet e tente de novo.',
  401: 'Sua sessão expirou. Entre de novo.',
  403: 'Você não tem permissão para fazer isso.',
  404: 'Não encontramos o que você procurou.',
  409: 'Alguém mudou este registro agora há pouco. Recarregue e tente de novo.',
  413: 'O arquivo é grande demais.',
  500: 'Algo deu errado do nosso lado. Tente de novo em instantes.',
  503: 'O serviço está indisponível agora. Tente de novo em instantes.',
};

export function paraErroDaApi(e: unknown): ErroDaApi {
  if (e instanceof ErroDaApi) return e;
  if (!(e instanceof HttpErrorResponse)) {
    return new ErroDaApi(0, 'erro-desconhecido', 'Algo deu errado. Tente de novo.', {});
  }
  const corpo = (typeof e.error === 'object' && e.error !== null ? e.error : {}) as ProblemDetails;
  const codigo = typeof corpo.type === 'string' && corpo.type.startsWith(BASE_TYPE)
    ? corpo.type.slice(BASE_TYPE.length)
    : `http-${e.status}`;
  let mensagem = typeof corpo.detail === 'string' && corpo.detail ? corpo.detail : '';
  if (codigo === 'validacao' && corpo.errors?.length) {
    mensagem = 'Confira os campos destacados.';
  }
  if (!mensagem) {
    mensagem = MENSAGEM_POR_STATUS[e.status] ?? MENSAGEM_POR_STATUS[e.status >= 500 ? 500 : 0] ?? 'Algo deu errado.';
  }
  return new ErroDaApi(e.status, codigo, mensagem, corpo);
}

/** Texto para mostrar a partir de qualquer erro (útil em `catch`). */
export function mensagemDe(e: unknown): string {
  return paraErroDaApi(e).mensagem;
}
