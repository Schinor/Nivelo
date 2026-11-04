/**
 * Compressão da foto no navegador, antes do upload: o canteiro tem sinal ruim e o disco é
 * da VM. Redimensiona para no máximo 1600 px no lado maior e grava em JPEG 0,8 (Parte A.8).
 */

export const LADO_MAXIMO = 1600;
export const QUALIDADE = 0.8;
export const TAMANHO_MAXIMO = 5 * 1024 * 1024;

/** Novas dimensões mantendo a proporção; imagem pequena não é ampliada. */
export function dimensoes(largura: number, altura: number, ladoMaximo = LADO_MAXIMO): { largura: number; altura: number } {
  const maior = Math.max(largura, altura);
  if (maior <= ladoMaximo) return { largura, altura };
  const escala = ladoMaximo / maior;
  return { largura: Math.round(largura * escala), altura: Math.round(altura * escala) };
}

export async function comprimir(arquivo: File): Promise<Blob> {
  if (!arquivo.type.startsWith('image/')) {
    throw new Error('Escolha um arquivo de imagem.');
  }
  // from-image: respeita a rotação EXIF da câmera do celular
  const imagem = await createImageBitmap(arquivo, { imageOrientation: 'from-image' });
  const { largura, altura } = dimensoes(imagem.width, imagem.height);
  const canvas = document.createElement('canvas');
  canvas.width = largura;
  canvas.height = altura;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Não foi possível preparar a foto neste aparelho.');
  ctx.drawImage(imagem, 0, 0, largura, altura);
  imagem.close();
  const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, 'image/jpeg', QUALIDADE));
  if (!blob) throw new Error('Não foi possível comprimir a foto.');
  if (blob.size > TAMANHO_MAXIMO) throw new Error('A foto ficou com mais de 5 MB mesmo comprimida.');
  return blob;
}
