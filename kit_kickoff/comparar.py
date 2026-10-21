"""Compara o motor da equipe com a resposta salva de POST /teste (relatório; sempre sai com 0).

  python comparar.py SUB.json RESPOSTA.json [--dados DIR] [--eventos FILE]

Salve a resposta com: python -m kickoff.api teste AG SUB.json --completo --salvar RESPOSTA.json
"""
import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from kickoff import medicao, motor, tempo, validar  # noqa: E402
from kickoff.dados import carregar  # noqa: E402
from simular import ler_eventos  # noqa: E402

TOL_ABS = 1e-6
TOL_REL_ENERGIA = 1e-2


def _dentro(chave, meu, juiz) -> bool:
    tol = max(TOL_ABS, TOL_REL_ENERGIA * abs(juiz)) if chave == "energia_kwh" else TOL_ABS
    return abs(meu - juiz) <= tol


def comparar_metricas(meu: dict, juiz: dict, diverge: list) -> None:
    print(f"{'métrica':<24}{'meu':>16}{'juiz':>16}{'diferença':>14}")
    for k in juiz:
        if k not in meu or isinstance(juiz[k], bool) or not isinstance(juiz[k], (int, float)):
            continue
        d = meu[k] - juiz[k]
        marca = "" if _dentro(k, meu[k], juiz[k]) else "  <--"
        print(f"{k:<24}{meu[k]:>16.4f}{juiz[k]:>16.4f}{d:>14.4f}{marca}")
        if marca:
            diverge.append(k)


def comparar_series(meu: dict, juiz: dict, diverge: list) -> None:
    print("\nséries (janelas de 15 min):")
    ini = juiz.get("inicio_min", meu["inicio_min"])
    for k in ("potencia_kw", "plugados_max", "fila_max"):
        if k not in juiz:
            continue
        a, b = meu[k], juiz[k]
        if len(a) != len(b):
            print(f"  {k}: tamanhos diferentes (meu {len(a)}, juiz {len(b)})")
            diverge.append(f"series.{k}")
            continue
        difs = [abs(x - y) for x, y in zip(a, b)]
        mx = max(difs, default=0.0)
        primeira = next((i for i, d in enumerate(difs) if d > TOL_ABS), None)
        onde = "" if primeira is None else f"; primeira divergência: {tempo.texto(ini + 15 * primeira)}"
        print(f"  {k}: diferença máx {mx:.6f}{onde}")
        if primeira is not None:
            diverge.append(f"series.{k}@{tempo.texto(ini + 15 * primeira)}")
    if "nao_atendidos_min" in juiz:
        a, b = meu["nao_atendidos_min"], juiz["nao_atendidos_min"]
        print(f"  nao_atendidos_min: meu {len(a)}, juiz {len(b)}")
        if len(a) != len(b):
            diverge.append("series.nao_atendidos_min")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python comparar.py")
    ap.add_argument("sub")
    ap.add_argument("resposta")
    ap.add_argument("--dados", type=Path, default=AQUI / "dados")
    ap.add_argument("--eventos")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    sub = json.loads(Path(a.sub).read_text(encoding="utf-8-sig"))
    resp = json.loads(Path(a.resposta).read_text(encoding="utf-8-sig"))
    ag = sub.get("agencia") or resp.get("agencia")
    sub = {**sub, "agencia": ag}
    cen = carregar(a.dados, ag)
    erros = validar.validar(sub, cen)
    if erros:
        print("submissão inválida:", *erros, sep="\n  ")
        return
    s = validar.normalizar(sub, cen)
    res = motor.simular(cen, s, [e for e in ler_eventos(a.eventos) if len(e) > 1 and e[1] == ag])
    ini, fim = tempo.JANELA_PUBLICA
    meu = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
    meu["demanda_contratada_kw"] = s["demanda_contratada_kw"] or 0.0
    diverge: list = []
    comparar_metricas(meu, resp.get("metricas") or {}, diverge)
    series = resp.get("series")
    if series:
        if "potencia_kw" not in series and "publico" in series:
            series = series["publico"]
        comparar_series(medicao.series(res.bins, res.trace, res.retiradas, res.nao_atendidos, ini, fim),
                        series, diverge)
    if res.violacoes:
        print("\nviolações no meu motor:", *res.violacoes[:10], sep="\n  ")
    print("\nOK: bate com o juiz" if not diverge else "\nDIVERGE em: " + ", ".join(diverge))


if __name__ == "__main__":
    main()
