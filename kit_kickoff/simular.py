"""Simula submissões na janela pública com o motor da equipe (kickoff/motor.py).

  python simular.py SUB.json [--dados DIR] [--catalogo FILE] [--eventos FILE] [--series]
"""
import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from kickoff import medicao, motor, nota, tempo, validar  # noqa: E402
from kickoff.dados import carregar  # noqa: E402

AVISO = ("nota não calculada: custos e pesos só saem em GET /catalogo depois de H4; "
         "salve a resposta em dados/catalogo.json e rode de novo.")


def ler_eventos(path) -> list:
    if not path:
        return []
    ev = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(ev, dict):
        ev = ev.get("eventos_ativos", [])
    return [list(e["params"]) if isinstance(e, dict) else list(e) for e in ev]


def tem_custos(cat, ag) -> bool:
    return bool(cat and cat.get("pesos", {}).get(ag)
                and all("custo" in c for c in cat.get("carregadores", ()) + cat.get("entradas", ())))


def avaliar(sub, cenarios: dict, dados: Path, cat, eventos, series: bool) -> dict:
    ag = sub.get("agencia") if isinstance(sub, dict) else None
    if not isinstance(ag, str):
        raise SystemExit("submissão sem 'agencia' (texto)")
    if ag not in cenarios:
        cenarios[ag] = carregar(dados, ag, cat)
    cen = cenarios[ag]
    erros = validar.validar(sub, cen)
    out = {"agencia": ag, "periodo": "publico", "valido": not erros, "erros": erros}
    if erros:
        return out
    s = validar.normalizar(sub, cen)
    res = motor.simular(cen, s, [e for e in eventos if len(e) > 1 and e[1] == ag])
    ini, fim = tempo.JANELA_PUBLICA
    m = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
    m["demanda_contratada_kw"] = s["demanda_contratada_kw"] or 0.0
    custo = nota.custo_infra(s, cen) if tem_custos(cat, ag) else None
    out["violacoes"] = res.violacoes
    if custo is not None:
        m["custo_infra"] = custo["total"]
        pontos = nota.pontuar(m, cat["pesos"][ag])
        out.update(metricas=m, pontos=pontos, nota=0 if res.violacoes else pontos["nota"], custo_infra=custo)
    else:
        out.update(metricas=m, nota=None, aviso=AVISO)
    if series:
        out["series"] = {"publico": medicao.series(res.bins, res.trace, res.retiradas, res.nao_atendidos, ini, fim)}
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python simular.py")
    ap.add_argument("sub", help="JSON com uma submissão ou lista de submissões")
    ap.add_argument("--dados", type=Path, default=AQUI / "dados")
    ap.add_argument("--catalogo", type=Path, help="padrão: <dados>/catalogo.json, se existir")
    ap.add_argument("--eventos", help="eventos_ativos de GET /status ou lista de params")
    ap.add_argument("--series", action="store_true")
    a = ap.parse_args(argv)
    cat_path = a.catalogo or a.dados / "catalogo.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8-sig")) if cat_path.exists() else None
    subs = json.loads(Path(a.sub).read_text(encoding="utf-8-sig"))
    eventos = ler_eventos(a.eventos)
    cenarios: dict = {}
    out = [avaliar(s, cenarios, a.dados, cat, eventos, a.series) for s in (subs if isinstance(subs, list) else [subs])]
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out if isinstance(subs, list) else out[0], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
