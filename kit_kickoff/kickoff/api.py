"""Cliente mínimo da API do juiz (urllib).

Limite: 20 req/min por equipe. Testes custam m7Coins, exceto em Bangkok (grátis, cooldown de 1 min).
Variáveis de ambiente: GAMEDAY_URL e GAMEDAY_TOKEN.

  python -m kickoff.api status
  python -m kickoff.api catalogo [arquivo]
  python -m kickoff.api kit AG
  python -m kickoff.api teste AG SUB.json [--completo] [--salvar F]
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RAIZ_KIT = Path(__file__).resolve().parent.parent
REFERER = "gameday.mobi7.io"


class ErroApi(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, corpo=None):
        super().__init__(f"{status} {codigo}: {mensagem}")
        self.status, self.codigo, self.mensagem, self.corpo = status, codigo, mensagem, corpo


class Cliente:
    def __init__(self, url=None, token=None):
        self.url = (url or os.environ.get("GAMEDAY_URL", "")).rstrip("/")
        self.token = token or os.environ.get("GAMEDAY_TOKEN", "")
        if not self.url or not self.token:
            raise SystemExit("defina GAMEDAY_URL e GAMEDAY_TOKEN (ou passe url= e token=)")

    def _req(self, metodo: str, caminho: str, corpo=None) -> bytes:
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(self.url + caminho, data=dados, method=metodo, headers={
            "Authorization": f"Bearer {self.token}",
            "Referer": REFERER,
            "User-Agent": "kickoff/1.0",
            **({"Content-Type": "application/json"} if dados is not None else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")
            try:
                j = json.loads(texto)
                raise ErroApi(e.code, j.get("codigo", f"http_{e.code}"), j.get("mensagem", ""), j) from None
            except ValueError:
                raise ErroApi(e.code, f"http_{e.code}", texto[:200], texto) from None

    def _json(self, metodo, caminho, corpo=None):
        return json.loads(self._req(metodo, caminho, corpo).decode("utf-8"))

    def status(self):
        return self._json("GET", "/status")

    def catalogo(self):
        return self._json("GET", "/catalogo")

    def agencia(self, ag: str):
        return self._json("GET", f"/agencias/{ag}")

    def contratos(self, ag: str):
        return self._json("GET", f"/agencias/{ag}/contratos")

    def frota_t0(self, ag: str):
        return self._json("GET", f"/agencias/{ag}/frota-t0")

    def baixar_kit(self, ag: str, destino=None) -> Path:
        """Baixa `/agencias/{ag}/kit` e extrai em `destino` (padrão: dados/ do kit). Devolve a pasta da agência."""
        destino = Path(destino) if destino else RAIZ_KIT / "dados"
        destino.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(self._req("GET", f"/agencias/{ag}/kit"))) as z:
            raiz = destino.resolve()
            for n in z.namelist():
                if not (raiz / n).resolve().is_relative_to(raiz):
                    raise ErroApi(0, "zip_invalido", f"caminho suspeito no zip: {n}")
            z.extractall(destino)
        return destino / ag

    def teste(self, ag: str, sub: dict, detalhe: str = "placar", salvar=None):
        r = self._json("POST", f"/teste/{ag}?detalhe={detalhe}", sub)
        if salvar:
            Path(salvar).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        return r


def main(argv=None) -> None:
    a = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    uso = "uso: python -m kickoff.api status | catalogo [arquivo] | kit AG | teste AG SUB.json [--completo] [--salvar F]"
    if not a:
        raise SystemExit(uso)
    cmd, resto = a[0], a[1:]
    salvar = None
    if "--salvar" in resto:
        i = resto.index("--salvar")
        salvar = resto[i + 1]
        del resto[i:i + 2]
    completo = "--completo" in resto
    resto = [x for x in resto if x != "--completo"]
    try:
        c = Cliente()
        if cmd == "status":
            print(json.dumps(c.status(), ensure_ascii=False, indent=1))
        elif cmd == "catalogo":
            cat = c.catalogo()
            if resto:
                Path(resto[0]).write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"catálogo salvo em {resto[0]}")
            else:
                print(json.dumps(cat, ensure_ascii=False, indent=1))
        elif cmd == "kit" and len(resto) == 1:
            print(f"kit extraído em {c.baixar_kit(resto[0])}")
        elif cmd == "teste" and len(resto) == 2:
            sub = json.loads(Path(resto[1]).read_text(encoding="utf-8-sig"))
            r = c.teste(resto[0], sub, "completo" if completo else "placar", salvar)
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            raise SystemExit(uso)
    except ErroApi as e:
        raise SystemExit(f"erro da API: {e}")


if __name__ == "__main__":
    main()
