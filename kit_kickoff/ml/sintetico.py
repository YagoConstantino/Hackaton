"""Agências e semanas sintéticas, a partir de uma agência real.

- criar(...): escreve dados/<novo>/ com contratos e frota multiplicados (com ruído), outro horário,
  outras vagas ou outra entrada. Serve para testar que o pipeline é genérico e para treinar modelos
  em agências diferentes das poucas reais.
- reamostrar_semanas(cen, seed): Cenario com as semanas públicas recombinadas por bootstrap
  (bloco = semana inteira). Serve para avaliar uma configuração em "semanas que não vimos".

  python3 -m ml.sintetico Bangkok Sintetica24h --escala 4 --vagas 4 --horario 24h
"""
from __future__ import annotations

import copy
import csv
import random
import shutil
from datetime import timedelta
from pathlib import Path

from kickoff import tempo
from kickoff.modelo import Agencia, Contrato

from .features import DADOS, carregar

DIAS_MD = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")
CATALOGO = ("veiculos.csv", "categorias.csv", "carregadores.csv", "entrada_eletrica.csv")


def _iso(t: float) -> str:
    return (tempo.EPOCA + timedelta(minutes=int(round(t)))).strftime("%Y-%m-%dT%H:%M:%S")


def _hhmm(m: int) -> str:
    return "23:59" if m >= 1440 else f"{m // 60:02d}:{m % 60:02d}"


def _horario(h):
    """'24h', None (mantém) ou lista de 7 itens (seg..dom) com (ini_min, fim_min) ou None."""
    if h == "24h":
        return [(0, 1440)] * 7
    return h


def criar(base: str, novo: str, escala: int = 1, vagas=None, horario=None, entrada=None,
          seed: int = 0, jitter_min: int = 90, dados_dir: Path = DADOS) -> Path:
    cen = carregar(base, dados_dir)
    rnd = random.Random(seed)
    ag = cen.agencia
    hor = _horario(horario) or ag.horario
    tmp = Agencia(novo, vagas or ag.vagas, 0, hor, ag.entrada_existente)
    pasta = Path(dados_dir) / novo
    if pasta.exists():
        shutil.rmtree(pasta)
    (pasta / "curvas").mkdir(parents=True)
    src = Path(dados_dir) / base
    for f in CATALOGO:
        shutil.copy(src / f, pasta / f)
    for f in (src / "curvas").glob("*.md"):
        shutil.copy(f, pasta / "curvas" / f.name)

    def mover(t):
        if t is None:
            return None, 0
        d = rnd.randint(-jitter_min, jitter_min)
        return (t + d, d) if tempo.aberta(tmp, t + d) else (t, 0)

    with open(pasta / "contratos_publicos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "categoria", "retirada", "devolucao", "autonomia_min_retirada_km", "km_devolucao"])
        for k in range(escala):
            for c in cen.contratos:
                ret, d = mover(c.retirada_t)
                if not tempo.aberta(tmp, ret):
                    continue  # novo horário não comporta esta retirada
                dev = None if c.devolucao_t is None else max(ret + 60, c.devolucao_t + d)
                km = None if c.km_devolucao is None else max(0.0, round(c.km_devolucao * rnd.uniform(0.9, 1.1)))
                w.writerow([f"{c.id}_{k}", c.categoria, _iso(ret), "" if dev is None else _iso(dev),
                            int(c.autonomia_min_retirada_km), "" if km is None else int(km)])
    n = 0
    with open(pasta / "frota_t0.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "modelo", "categoria", "situacao", "soc_pct", "devolucao_prevista", "soc_devolucao_pct"])
        for k in range(escala):
            for v in cen.veiculos:
                n += 1
                vid = f"V{k}{v.id[1:]}"
                if v.situacao == "em_contrato":
                    dev = max(tempo.T0, v.devolucao_t + rnd.randint(-jitter_min, jitter_min))
                    w.writerow([vid, v.modelo, v.categoria, v.situacao, "", _iso(dev), v.soc_devolucao])
                else:
                    w.writerow([vid, v.modelo, v.categoria, v.situacao, v.soc, "", ""])
    ent = cen.entradas[entrada or ag.entrada_existente]
    linhas = [f"# {novo}", "", "| Item | Valor |", "|---|---|", f"| Vagas elétricas | {tmp.vagas} |",
              f"| Frota | {n} |", f"| Entrada existente | {ent.descricao} ({ent.kva:g} kVA, {ent.kw_util:g} kW úteis) |",
              "", "## Horário de abertura", "", "| Dia | Horário |", "|---|---|"]
    for i in (6, 0, 1, 2, 3, 4, 5):
        j = hor[i]
        linhas.append(f"| {DIAS_MD[i]} | {'fechado' if j is None else _hhmm(j[0]) + '-' + _hhmm(j[1])} |")
    (pasta / "agencias.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return pasta


def reamostrar_semanas(cen, seed: int):
    """Cópia do cenário com cada semana pública substituída por uma semana sorteada (com reposição).
    Contratos deslocados em semanas inteiras mantêm dia da semana e hora. A frota em T0 não muda."""
    rnd = random.Random(seed)
    sem = 7 * tempo.DIA
    blocos = {k: [c for c in cen.contratos if tempo.T0 + k * sem <= c.retirada_t < tempo.T0 + (k + 1) * sem]
              for k in range(4)}
    novos = []
    for alvo in range(4):
        fonte = rnd.randrange(4)
        d = (alvo - fonte) * sem
        for c in blocos[fonte]:
            novos.append(Contrato(f"{c.id}_s{alvo}", c.categoria, c.rank, c.retirada_t + d,
                                  None if c.devolucao_t is None else c.devolucao_t + d,
                                  c.autonomia_min_retirada_km, c.km_devolucao))
    novos.sort(key=lambda c: (c.retirada_t, c.id))
    out = copy.copy(cen)
    out.contratos = novos
    return out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m ml.sintetico")
    ap.add_argument("base")
    ap.add_argument("novo")
    ap.add_argument("--escala", type=int, default=1)
    ap.add_argument("--vagas", type=int)
    ap.add_argument("--horario", choices=["24h"])
    ap.add_argument("--entrada")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    p = criar(a.base, a.novo, a.escala, a.vagas, a.horario, a.entrada, a.seed)
    from kickoff import dados
    print(f"criada em {p}\n" + dados.resumo(dados.carregar(DADOS, a.novo)))


if __name__ == "__main__":
    main()
