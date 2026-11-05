"""Navegação do Nivelo num celular (390 px), com Playwright, tirando um print de cada tela.

Dois roteiros, em dois passos, porque o cliente só entra pelo link do convite:

- ``dono``: landing → cadastro → primeira obra → registrar o dia com foto → publicar → foto depois
  da publicação → revisão com motivo → abas da obra → convite do cliente → limite do plano (402).
- ``cliente``: aceite do convite → login → obra → diário publicado com as fotos, sem os
  controles de escrita → comentário.

Cada print confere que a tela não rola na horizontal. O roteiro ``dono`` grava o e-mail do
cliente e as URLs da obra e do diário em ``<saida>/estado.json``, lido pelo roteiro ``cliente``.

Uso (ver e2e/README.md):
    python navegar.py dono --base https://nivelo.exemplo --email-dono d@x --email-cliente c@x
    python navegar.py cliente --base https://nivelo.exemplo --token <token do link do convite>
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, Playwright, expect, sync_playwright

LARGURA = 390
ALTURA = 844
UUID = r"[0-9a-f-]{36}"


class Roteiro:
    def __init__(self, args: argparse.Namespace) -> None:
        self.base = args.base.rstrip("/")
        self.saida = Path(args.saida)
        self.saida.mkdir(parents=True, exist_ok=True)
        self.estado = self.saida / "estado.json"
        self.passo = 0 if args.roteiro == "dono" else 20
        self.erros_no_console: list[str] = []
        self.atual: Page | None = None

    def pagina(self, p: Playwright) -> Page:
        navegador = p.chromium.launch()
        contexto = navegador.new_context(
            viewport={"width": LARGURA, "height": ALTURA},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="pt-BR",
            # O "hoje" da API é o do fuso do negócio; sem isto, o Chromium em UTC manda o dia seguinte
            # depois das 21h e o diário volta 422 (data futura).
            timezone_id="America/Sao_Paulo",
        )
        pag = contexto.new_page()
        pag.on("console", lambda m: m.type == "error" and self.erros_no_console.append(m.text))
        self.atual = pag
        return pag

    def foto(self, pag: Page, nome: str) -> None:
        self.passo += 1
        pag.wait_for_timeout(400)
        pag.screenshot(path=str(self.saida / f"{self.passo:02d}-{nome}.png"), full_page=True)
        largura = pag.evaluate("document.documentElement.scrollWidth")
        assert largura <= LARGURA + 1, f"{nome}: rolagem horizontal ({largura}px)"
        print(f"  [ok] {self.passo:02d} {nome} (largura {largura}px)")


def jpeg(caminho: Path, cor: tuple[int, int, int]) -> None:
    """Foto grande (4000x3000), para conferir que o navegador comprime para 1600 px."""
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), cor).save(buf, "JPEG", quality=95)
    caminho.write_bytes(buf.getvalue())


def dono(r: Roteiro, p: Playwright, args: argparse.Namespace) -> None:
    pasta = Path(tempfile.mkdtemp(prefix="nivelo-e2e-"))
    canteiro, depois = pasta / "canteiro.jpg", pasta / "depois.jpg"
    jpeg(canteiro, (170, 120, 70))
    jpeg(depois, (60, 110, 160))
    pag = r.pagina(p)

    pag.goto(r.base + "/")
    expect(pag.get_by_role("heading", name="Cada dia de obra registrado. Cada cliente por dentro.")).to_be_visible()
    expect(pag.get_by_text("R$ 29,90", exact=True)).to_be_visible()
    expect(pag.get_by_text("R$ 69,90", exact=True)).to_be_visible()
    r.foto(pag, "landing")

    pag.get_by_role("link", name="Criar conta grátis").first.click()
    pag.wait_for_url("**/cadastro")
    pag.get_by_text("Autônomo", exact=True).click()
    pag.fill("#org", args.empresa)
    pag.fill("#nome", args.nome_dono)
    pag.fill("#email", args.email_dono)
    pag.fill("#senha", args.senha)
    r.foto(pag, "cadastro")
    pag.locator("form button[type=submit]").click()
    # Passo 2 de 2: o cadastro leva direto para a primeira obra
    pag.wait_for_url("**/obras/nova")
    expect(pag.get_by_text("Passo 2 de 2")).to_be_visible()
    pag.fill("#nome", args.obra)
    pag.fill("#cliente", args.nome_cliente)
    pag.fill("#logradouro", "Rua das Acácias, 120")
    pag.fill("#cidade", "Marília")
    pag.fill("#termino", "2027-03-31")
    r.foto(pag, "obra-nova")
    pag.get_by_role("button", name="Cadastrar obra").click()
    pag.wait_for_url(re.compile(rf"/obras/{UUID}$"))
    obra_url = pag.url
    expect(pag.get_by_role("heading", name=args.obra)).to_be_visible()
    r.foto(pag, "obra-detalhe")

    pag.goto(r.base + "/obras")
    expect(pag.get_by_text(args.obra).first).to_be_visible()
    r.foto(pag, "obras")
    pag.goto(obra_url)

    pag.get_by_role("link", name="Registrar o dia de hoje").first.click()
    pag.locator("fieldset", has_text="Manhã").get_by_text("Sol", exact=True).click()
    pag.locator("fieldset", has_text="Tarde").get_by_text("Chuva", exact=True).click()
    for _ in range(4):
        pag.get_by_role("button", name="Aumentar").click()
    pag.fill("#nova-at", "Demolição da parede da cozinha")
    pag.get_by_role("button", name="Adicionar atividade").click()
    pag.fill("#nova-at", "Retirada do entulho")
    pag.keyboard.press("Enter")
    expect(pag.locator(".lista-atividades li")).to_have_count(2)
    pag.get_by_text("Sim", exact=True).click()
    pag.get_by_role("button", name="Chuva", exact=True).click()
    pag.fill("#oc-desc-0", "Chuva forte às 15h, serviço externo parado")
    pag.fill("#oc-imp-0", "1")
    pag.locator("app-seletor-de-fotos input[type=file]").set_input_files(str(canteiro))
    expect(pag.locator(".previas img")).to_have_count(1)
    r.foto(pag, "diario-formulario")
    pag.get_by_role("button", name="Publicar o dia").click()
    pag.wait_for_url(re.compile(rf"/diarios/{UUID}$"))
    diario_url = pag.url
    expect(pag.locator(".selo-publicado")).to_be_visible()
    expect(pag.locator("app-galeria img")).to_have_count(1)
    pag.wait_for_function("document.querySelector('app-galeria img')?.naturalWidth > 0")
    largura_foto = pag.evaluate("document.querySelector('app-galeria img').naturalWidth")
    assert largura_foto == 1600, f"a foto não foi comprimida para 1600 px: {largura_foto}"
    r.foto(pag, "diario-publicado-com-foto")

    pag.locator("app-seletor-de-fotos input[type=file]").set_input_files(str(depois))
    # Comprimir 4000 px no navegador e enviar leva alguns segundos
    expect(pag.locator("app-galeria img")).to_have_count(2, timeout=30_000)
    expect(pag.get_by_text("Adicionada após a publicação").first).to_be_visible()
    r.foto(pag, "foto-apos-publicacao")

    pag.get_by_role("button", name="Revisar diário").click()
    pag.fill("#motivo", "Faltou contar o ajudante que chegou às 9h")
    r.foto(pag, "revisao-motivo")
    pag.get_by_role("button", name="Continuar para edição").click()
    expect(pag.locator("#motivo")).to_have_value("Faltou contar o ajudante que chegou às 9h")
    pag.get_by_role("button", name="Aumentar").click()
    r.foto(pag, "revisao-formulario")
    pag.get_by_role("button", name="Salvar revisão").click()
    pag.wait_for_url(diario_url)
    expect(pag.get_by_text("Faltou contar o ajudante").first).to_be_visible()
    expect(pag.locator(".selo-revisado")).to_be_visible()
    r.foto(pag, "diario-revisado")

    pag.goto(obra_url)
    for aba, nome in (("Fotos", "obra-aba-fotos"), ("Ocorrências", "obra-aba-ocorrencias"), ("Histórico", "obra-aba-historico")):
        pag.get_by_role("tab", name=re.compile(aba)).click()
        pag.wait_for_timeout(600)
        r.foto(pag, nome)
    pag.get_by_role("tab", name=re.compile("Ocorrências")).click()
    expect(pag.get_by_text("Chuva forte às 15h")).to_be_visible()
    pag.get_by_role("tab", name=re.compile("Pessoas da obra")).click()
    r.foto(pag, "obra-aba-pessoas")
    pag.get_by_role("link", name="Convidar cliente").click()
    pag.wait_for_url("**/equipe**")
    pag.fill("#email", args.email_cliente)
    expect(pag.locator("#papel")).to_have_value("cliente")
    r.foto(pag, "equipe-convite")
    pag.get_by_role("button", name="Enviar convite").click()
    expect(pag.get_by_text("Convite enviado")).to_be_visible(timeout=30_000)

    # Free: uma obra ativa. A segunda esbarra no limite (402) e abre o modal.
    pag.goto(r.base + "/obras/nova")
    pag.fill("#nome", "Muro da escola")
    pag.fill("#cliente", "Escola")
    pag.fill("#logradouro", "Rua 2")
    pag.fill("#cidade", "Marília")
    pag.fill("#termino", "2027-01-31")
    pag.get_by_role("button", name="Cadastrar obra").click()
    expect(pag.get_by_role("dialog").get_by_text("Assinar o Pro")).to_be_visible()
    r.foto(pag, "limite-do-plano-402")

    estado = {"cliente": args.email_cliente, "obra": args.obra, "obra_url": obra_url, "diario_url": diario_url}
    r.estado.write_text(json.dumps(estado, ensure_ascii=False, indent=2))


def cliente(r: Roteiro, p: Playwright, args: argparse.Namespace) -> None:
    estado = json.loads(r.estado.read_text())
    pag = r.pagina(p)

    pag.goto(f"{r.base}/convite?token={args.token}")
    pag.fill("#nome", args.nome_cliente)
    pag.fill("#senha", args.senha)
    r.foto(pag, "convite-aceite")
    pag.get_by_role("button", name="Aceitar convite").click()
    pag.wait_for_url("**/login")
    pag.fill("#email", estado["cliente"])
    pag.fill("#senha", args.senha)
    pag.locator("form button[type=submit]").click()
    pag.wait_for_url("**/obras")
    expect(pag.get_by_text(estado["obra"]).first).to_be_visible()
    expect(pag.get_by_role("link", name="Nova obra")).to_have_count(0)
    expect(pag.get_by_role("link", name=re.compile("Registrar o dia"))).to_have_count(0)
    r.foto(pag, "cliente-obras")

    pag.get_by_text(estado["obra"]).first.click()
    expect(pag.get_by_role("link", name=re.compile("Registrar o dia"))).to_have_count(0)
    expect(pag.get_by_role("link", name="Editar obra")).to_have_count(0)
    expect(pag.get_by_role("tab", name=re.compile("Histórico"))).to_have_count(0)
    expect(pag.get_by_role("button", name=re.compile("Remover"))).to_have_count(0)
    r.foto(pag, "cliente-obra")

    pag.goto(estado["diario_url"])
    expect(pag.locator("app-galeria img")).to_have_count(2)
    pag.wait_for_function("[...document.querySelectorAll('app-galeria img')].every(i => i.naturalWidth > 0)")
    expect(pag.get_by_text("Adicionada após a publicação").first).to_be_visible()
    for proibido in ("Publicar o dia", "Revisar diário", "Adicionar fotos", "Remover rascunho"):
        assert pag.get_by_text(proibido).count() == 0, f"o cliente vê um controle de escrita: {proibido}"
    pag.fill("#comentario", "Obrigado! Pode seguir com o contrapiso quando secar.")
    pag.get_by_role("button", name="Comentar").click()
    expect(pag.get_by_text("Pode seguir com o contrapiso")).to_be_visible()
    r.foto(pag, "cliente-diario-publicado")


def argumentos(argv: list[str]) -> argparse.Namespace:
    agora = int(time.time())
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roteiro", choices=["dono", "cliente"])
    ap.add_argument("--base", required=True, help="URL base, ex.: http://localhost:8000 ou a URL de produção")
    ap.add_argument("--saida", default="prints", help="pasta dos prints e do estado.json (padrão: prints)")
    ap.add_argument("--senha", default="senha-do-roteiro-e2e", help="senha do dono e do cliente")
    ap.add_argument("--email-dono", default=f"valdir-{agora}@exemplo.com")
    ap.add_argument("--email-cliente", default=f"jorge-{agora}@exemplo.com")
    ap.add_argument("--nome-dono", default="Valdir Rocha")
    ap.add_argument("--empresa", default="Rocha Reformas")
    ap.add_argument("--nome-cliente", default="Jorge Alves")
    ap.add_argument("--obra", default="Reforma da casa do Jorge")
    ap.add_argument("--token", help="token do link do convite (roteiro cliente)")
    args = ap.parse_args(argv)
    if args.roteiro == "cliente" and not args.token:
        ap.error("o roteiro cliente precisa do --token do link do convite")
    return args


def main(argv: list[str]) -> int:
    args = argumentos(argv)
    r = Roteiro(args)
    with sync_playwright() as p:
        try:
            (dono if args.roteiro == "dono" else cliente)(r, p, args)
        except Exception:
            if r.atual is not None:
                r.atual.screenshot(path=str(r.saida / "erro.png"), full_page=True)
                print(f"Falhou em {r.atual.url}; print da tela em {r.saida / 'erro.png'}", file=sys.stderr)
            raise
    if r.erros_no_console:
        print("Erros no console do navegador (o 402 do limite do plano é esperado):")
        for erro in r.erros_no_console:
            print("  ", erro)
    print(f"OK: prints em {r.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
