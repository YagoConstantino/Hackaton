"""Mostra, janela a janela, onde a série do motor difere da do juiz.

  python3 validacao/diag_series.py validacao/01_exemplo.json [serie] [n_linhas]
  serie: fila_max (padrão), plugados_max ou potencia_kw
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, medicao, motor, tempo, validar  # noqa: E402


def main() -> None:
    sub_path = Path(sys.argv[1])
    serie = sys.argv[2] if len(sys.argv) > 2 else "fila_max"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    resp = json.loads((sub_path.parent / "respostas" / sub_path.name).read_text(encoding="utf-8"))
    juiz = resp["series"]
    juiz = juiz.get("publico", juiz)
    sub = json.loads(sub_path.read_text(encoding="utf-8"))
    cen = dados.carregar(RAIZ / "dados", sub["agencia"])
    res = motor.simular(cen, validar.normalizar(sub, cen))
    ini, fim = tempo.JANELA_PUBLICA
    meu = medicao.series(res.bins, res.trace, res.retiradas, res.nao_atendidos, ini, fim)
    a, b = meu[serie], juiz[serie]
    difs = [k for k in range(min(len(a), len(b))) if abs(a[k] - b[k]) > 1e-6]
    print(f"{serie}: {len(difs)} janelas diferentes de {len(b)}; "
          f"soma meu={sum(a):.1f} juiz={sum(b):.1f}; máx meu={max(a)} juiz={max(b)}")
    if not difs:
        return
    k0 = max(0, difs[0] - 8)
    print(f"\n{'janela':<18}{'plug meu':>9}{'plug juiz':>10}{'fila meu':>9}{'fila juiz':>10}{'kW meu':>9}{'kW juiz':>9}")
    for k in range(k0, min(len(b), k0 + n)):
        marca = "  <--" if k in difs else ""
        print(f"{tempo.texto(ini + 15 * k):<18}{meu['plugados_max'][k]:>9}{juiz['plugados_max'][k]:>10}"
              f"{meu['fila_max'][k]:>9}{juiz['fila_max'][k]:>10}"
              f"{meu['potencia_kw'][k]:>9.2f}{juiz['potencia_kw'][k]:>9.2f}{marca}")
    # padrão da diferença ao longo do mês
    d = [a[k] - b[k] for k in range(min(len(a), len(b)))]
    print("\ndiferença (meu - juiz): distribuição", {v: d.count(v) for v in sorted(set(d))})


if __name__ == "__main__":
    main()
