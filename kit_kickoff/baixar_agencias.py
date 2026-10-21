"""Baixa o kit de todas as agências liberadas (GET /status) para dados/<Agencia>/.

  python3 baixar_agencias.py                  # baixa as que ainda não existem em dados/
  python3 baixar_agencias.py --forcar         # baixa de novo todas (sobrescreve)
  python3 baixar_agencias.py Istanbul Hanoi   # só essas
  python3 baixar_agencias.py --catalogo       # também salva GET /catalogo em dados/catalogo.json

Exige GAMEDAY_URL e GAMEDAY_TOKEN. Não gasta m7Coins (kit, status e catálogo são grátis).
A rota /kit devolve o zip codificado em base64 (como no exemplo de curl das docs); este script
aceita zip cru, base64 cru, base64 entre aspas e JSON com o base64 num campo.
"""
import base64
import binascii
import io
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from kickoff import dados  # noqa: E402
from kickoff.api import Cliente, ErroApi  # noqa: E402

DADOS = AQUI / "dados"
PAUSA_S = 3.5  # limite da API: 20 req/min por equipe (somando todos os membros)


def para_zip(corpo: bytes) -> bytes:
    """Bytes do zip a partir da resposta da rota /kit, em qualquer dos formatos aceitos."""
    if corpo[:2] == b"PK":
        return corpo
    texto = corpo.decode("utf-8", "replace").strip()
    if texto.startswith(("{", '"')):
        try:
            j = json.loads(texto)
        except ValueError:
            j = None
        if isinstance(j, str):
            texto = j
        elif isinstance(j, dict):
            if "codigo" in j and "mensagem" in j:
                raise ErroApi(0, j["codigo"], j["mensagem"], j)
            campo = next((v for v in j.values() if isinstance(v, str) and len(v) > 100), None)
            if campo is None:
                raise ValueError(f"JSON sem campo com o zip: chaves {list(j)}")
            texto = campo
    try:
        z = base64.b64decode("".join(texto.split()), validate=False)
    except binascii.Error as e:
        raise ValueError(f"resposta não é zip nem base64: {texto[:80]!r}") from e
    if z[:2] != b"PK":
        raise ValueError(f"base64 decodificado não é zip (início {z[:8]!r})")
    return z


def eh_curva(p: Path) -> bool:
    """Arquivo de curva = tabela com 21 linhas de SOC (0%, 5%, ..., 100%)."""
    linhas = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    return sum(1 for ln in linhas if re.match(r"^\|\s*\d+%\s*\|", ln.strip())) == 21


def extrair(zbytes: bytes, ag: str, destino_dados: Path) -> Path:
    """Extrai em dados/<ag>/, aceitando zip com pasta <ag>/, com outra pasta única ou com arquivos soltos."""
    pasta = destino_dados / ag
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        nomes = [n for n in z.namelist() if not n.endswith("/") and not n.startswith("__MACOSX")]
        topos = {n.split("/", 1)[0] for n in nomes}
        prefixo = ""
        if len(topos) == 1 and all("/" in n for n in nomes):
            prefixo = next(iter(topos)) + "/"  # pasta única (normalmente <ag>/): remove
        if pasta.exists():
            shutil.rmtree(pasta)
        pasta.mkdir(parents=True)
        raiz = pasta.resolve()
        for n in nomes:
            rel = n[len(prefixo):]
            alvo = (pasta / rel).resolve()
            if not alvo.is_relative_to(raiz):
                raise ValueError(f"caminho suspeito no zip: {n}")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(z.read(n))
    # curvas soltas na raiz (sem a pasta curvas/): move para curvas/
    curvas = pasta / "curvas"
    soltas = [p for p in pasta.glob("*.md") if eh_curva(p)]
    if soltas and not curvas.is_dir():
        curvas.mkdir()
        for p in soltas:
            p.rename(curvas / p.name)
    return pasta


def main() -> None:
    args = sys.argv[1:]
    forcar = "--forcar" in args
    com_catalogo = "--catalogo" in args
    pedidas = [a for a in args if not a.startswith("--")]
    sys.stdout.reconfigure(encoding="utf-8")
    c = Cliente()
    st = c.status()
    liberadas = list(st.get("agencias", {}))
    print(f"fase: {st.get('fase')} | saldo: {st.get('saldo')} m7Coins | liberadas: {', '.join(liberadas)}")
    if st.get("eventos_ativos"):
        print(f"ATENÇÃO, eventos ativos: {st['eventos_ativos']}")
    alvo = [a for a in liberadas if not pedidas or a in pedidas]
    for a in pedidas:
        if a not in liberadas:
            print(f"{a}: não liberada (ou nome diferente); ignorando")
    DADOS.mkdir(exist_ok=True)
    for ag in alvo:
        if (DADOS / ag / "contratos_publicos.csv").exists() and not forcar:
            print(f"{ag}: já existe em dados/{ag} (use --forcar para baixar de novo)")
            continue
        time.sleep(PAUSA_S)
        try:
            pasta = extrair(para_zip(c._req("GET", f"/agencias/{ag}/kit")), ag, DADOS)
        except (ErroApi, ValueError, zipfile.BadZipFile) as e:
            print(f"{ag}: FALHOU ({e})")
            continue
        try:
            print(f"{ag}: ok em {pasta}\n  " + dados.resumo(dados.carregar(DADOS, ag)).replace("\n", "\n  "))
        except SystemExit as e:
            print(f"{ag}: baixado, mas o leitor do kit reclamou:\n  {e}\n  arquivos: "
                  + ", ".join(sorted(str(p.relative_to(pasta)) for p in pasta.rglob("*") if p.is_file())))
    if com_catalogo:
        time.sleep(PAUSA_S)
        cat = c.catalogo()
        (DADOS / "catalogo.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
        tem = bool(cat.get("pesos")) and all("custo" in x for x in cat.get("carregadores", []))
        print(f"catálogo salvo em dados/catalogo.json ({'com' if tem else 'SEM'} custos e pesos"
              f"{'' if tem else ' — normal antes de H4'})")


if __name__ == "__main__":
    main()
