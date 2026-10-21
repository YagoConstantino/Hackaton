"""Roda a bateria validacao/*.json no juiz (SÓ Bangkok, grátis) e compara com o motor.

  python validacao/validar_juiz.py            # todas, com 65 s entre testes (cooldown de 1 min)
  python validacao/validar_juiz.py 03 06      # só as que começam com esses prefixos
  python validacao/validar_juiz.py --local    # sem API: só compara com respostas já salvas

Exige GAMEDAY_URL e GAMEDAY_TOKEN. Respostas em validacao/respostas/<nome>.json.
Teste idêntico já feito não é cobrado nem consome cooldown.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))


def main() -> None:
    args = sys.argv[1:]
    local = "--local" in args
    prefixos = [a for a in args if not a.startswith("--")]
    subs = sorted(p for p in AQUI.glob("*.json") if not prefixos or any(p.name.startswith(x) for x in prefixos))
    (AQUI / "respostas").mkdir(exist_ok=True)
    resumo = []
    for i, p in enumerate(subs):
        sub = json.loads(p.read_text(encoding="utf-8"))
        if sub.get("agencia") != "Bangkok":
            raise SystemExit(f"{p.name}: só Bangkok é grátis; recusando para não gastar m7Coins")
        resp = AQUI / "respostas" / p.name
        if not local:
            from kickoff.api import Cliente, ErroApi
            if i:
                time.sleep(65)
            try:
                Cliente().teste("Bangkok", sub, "completo", resp)
            except ErroApi as e:
                print(f"{p.name}: erro da API: {e}")
                continue
        if not resp.exists():
            print(f"{p.name}: sem resposta salva")
            continue
        out = subprocess.run([sys.executable, str(RAIZ / "comparar.py"), str(p), str(resp)],
                             capture_output=True, text=True, encoding="utf-8").stdout
        ultima = out.strip().splitlines()[-1] if out.strip() else "(sem saída)"
        print(f"\n===== {p.name}\n{out}")
        resumo.append((p.name, ultima))
    print("\n===== RESUMO")
    for n, r in resumo:
        print(f"{n:<28} {r}")


if __name__ == "__main__":
    main()
