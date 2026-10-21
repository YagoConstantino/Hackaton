"""Roda a análise de ML de uma agência e grava ml/saida/<Agencia>/relatorio.md (+ CSVs).

  python3 -m ml.rodar Istanbul                         # tudo, 300 simulações para o surrogate
  python3 -m ml.rodar Hanoi --amostras 500 --cenarios 5
  python3 -m ml.rodar Zurich --etapas curvas,energia   # só algumas etapas
  python3 -m ml.rodar --todas --amostras 200           # todas as agências em dados/

Etapas: ficha, curvas, energia, nao_supervisionado, carregadores. Não chama a API.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

from . import carregadores as C
from . import energia as E
from . import features as F
from . import nao_supervisionado as U

ETAPAS = ("ficha", "curvas", "energia", "nao_supervisionado", "carregadores")
SAIDA = Path(__file__).resolve().parent / "saida"


def _md(df: pd.DataFrame, casas=2) -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].round(casas)
    cols = [str(c) for c in d.columns]
    linhas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    linhas += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join(linhas)


def _serie_md(s: pd.Series, nome="valor", n=10) -> str:
    return _md(s.head(n).rename(nome).reset_index().rename(columns={"index": "feature"}), 3)


def analisar(agencia: str, etapas=ETAPAS, amostras=300, top=10, cenarios=0, workers=None, catalogo=None,
             entradas="auto", incluir_nao_validadas=False) -> Path:
    warnings.filterwarnings("ignore")
    t0 = time.time()
    out_dir = SAIDA / agencia
    out_dir.mkdir(parents=True, exist_ok=True)
    cen = F.carregar(agencia)
    res = F.simular(cen)
    sess = F.sessoes_energia(cen, res)
    md = [f"# Análise de ML — {agencia}", "",
          "Gerado por `python3 -m ml.rodar`. Rótulos vêm do motor (validado contra o juiz em Bangkok). "
          "Nenhuma chamada à API.", ""]

    if "ficha" in etapas:
        fi = F.ficha_agencia(cen)
        md += ["## Ficha", "", _md(pd.DataFrame([(k, str(v)) for k, v in fi.items()], columns=["item", "valor"])), ""]

    if "curvas" in etapas:
        tm, info = U.agrupar_modelos(cen)
        tm.to_csv(out_dir / "modelos_curvas.csv", index=False)
        md += ["## Curvas de recarga (não supervisionado)", "",
               f"KMeans com k={info['k']} (silhueta {info['silhueta']:.2f}); PCA explica "
               f"{info['pca_variancia']} da variância.", "",
               _md(tm[["modelo", "categoria", "frota_n", "ac_kw", "dc_pico_kw", "dc_medio_20_80", "dc_queda",
                       "classe_recarga_nome", "carregador_suficiente"]]), "",
               "Energia de recarga por classe (quanto da demanda cada tipo de curva gera):", "",
               _md(U.energia_por_classe(tm, sess), 1), ""]

    if "energia" in etapas:
        ac = E.avaliar_contratos(cen, res)
        ad = E.avaliar_dias(cen, res)
        pl = E.potencia_livre(cen)
        ps = E.perfil_semanal(cen, res)
        ps.to_csv(out_dir / "perfil_semanal_kwh.csv", index=False)
        ac["dados"].to_csv(out_dir / "contratos_rotulados.csv", index=False)
        md += ["## Energia", "", f"### Por contrato (n={ac['n']}, validação deixando 1 semana de fora)", "",
               _md(ac["metricas"].reset_index().rename(columns={"index": "modelo"}), 3), "",
               "Importância por permutação (aumento do erro em kWh ao embaralhar a feature) — GBM só com dados brutos:", "",
               _serie_md(ac["importancia_gbm_bruto"], "delta_MAE_kWh"), "",
               "Informação mútua com o kWh real:", "", _serie_md(ac["informacao_mutua"], "info_mutua"), "",
               f"### Por dia (n={ad['n']})", "",
               _md(ad["metricas"].reset_index().rename(columns={"index": "modelo"}), 3), "",
               "### Potência pedida sem limite de entrada", "",
               f"Com {pl['carregadores']} e {pl['entrada']}: pico {pl['pico_kw']:.1f} kW; "
               f"P50 {pl.get('P50', 0):.1f}, P90 {pl.get('P90', 0):.1f}, P95 {pl.get('P95', 0):.1f}, "
               f"P99 {pl.get('P99', 0):.1f} kW (janelas com carga); "
               f"carga em {pl['horas_com_carga_pct']:.0f}% do tempo; perdidos sem limite: "
               f"{pl['nao_atendidos_sem_limite']}, upgrades: {pl['upgrades_sem_limite']}.", "",
               "Horas da semana com mais energia chegando (média das semanas públicas):", "",
               _md(ps.sort_values("kwh_media", ascending=False).head(10), 1), ""]

    if "nao_supervisionado" in etapas:
        ct = F.contratos_rotulados(cen, res)
        _, perf, i2 = U.agrupar_contratos(ct)
        _, perf_d, i3 = U.agrupar_dias(F.tabela_dias(cen))
        an = U.anomalias(ct)
        an.to_csv(out_dir / "contratos_anomalos.csv", index=False)
        md += ["## Segmentos e tipos de dia (não supervisionado)", "",
               f"### Segmentos de contrato (k={i2['k']}, silhueta {i2['silhueta']:.2f})", "", _md(perf), "",
               f"### Tipos de dia (k={i3['k']}, silhueta {i3['silhueta']:.2f})", "", _md(perf_d, 1), "",
               f"### Anomalias: {len(an)} contratos fora do padrão (IsolationForest) — ver `contratos_anomalos.csv`", ""]

    if "carregadores" in etapas:
        t = time.time()
        ents = C.entradas_auto(cen) if entradas == "auto" else [(cen.agencia.entrada_existente, None)]
        df = C.gerar_dataset(cen, n=amostras, entradas=ents, workers=workers)
        df.to_csv(out_dir / "dataset_surrogate.csv", index=False)
        mods = C.treinar(df)
        pols = C.POLITICAS if incluir_nao_validadas else C.POLITICAS_VALIDADAS
        rec = C.recomendar(cen, mods, top=top, cat=catalogo, cenarios=cenarios, workers=workers,
                           entradas=[(cen.agencia.entrada_existente, None)], politicas=pols)
        por_ent = {}
        if len(ents) > 1:
            for ev in (False, True):
                pe = [p for p in pols if p["evitar_ponta"] == ev]
                por_ent[ev] = C.melhor_por_entrada(cen, mods, ents, politicas=pe, cenarios=cenarios, workers=workers)
        rec.drop(columns=["submissao"]).to_csv(out_dir / "recomendacoes.csv", index=False)
        (out_dir / "submissoes_candidatas.json").write_text(
            json.dumps(list(rec.submissao), ensure_ascii=False, indent=1), encoding="utf-8")
        pred = C.prever_todos(cen, mods)
        fr = C.fronteira(pred)
        qual = pd.DataFrame([{"métrica": a, "R2_cv": i["R2_cv"], "MAE_cv": i["MAE_cv"], "média": i["media_y"]}
                             for a, i in mods.items()])
        cols = [c for c in ("config", "pol_prioridade", "pol_divisao", "pol_evitar_ponta", "kw_nominal", "nao_atendidos",
                            "upgrades", "energia_ponta_kwh", "pico_kw", "perdidos_media_reamostr",
                            "perdidos_pior_reamostr", "nota_estimada") if c in rec]
        md += ["## Carregadores (surrogate supervisionado)", "",
               f"{len(df)} simulações em {time.time() - t:.0f} s; {len(C.combos(cen))} combinações × "
               f"{len(C.POLITICAS)} políticas previstas.", "", "Qualidade (validação cruzada 5 dobras):", "", _md(qual, 3), "",
               "O que mais pesa nos clientes perdidos (importância por permutação):", "",
               _serie_md(mods["nao_atendidos"]["importancia"], "delta_MAE"), "",
               "### Melhores candidatos (confirmados no motor)", "",
               "Sem catálogo com custos (Neblina), a ordem é: menos perdidos → menos upgrades → menos kW instalado.", "",
               _md(rec[cols], 1), "", "Submissões prontas em `submissoes_candidatas.json` (testar com `simular.py`).", ""]
        if por_ent:
            todas = pd.concat(por_ent.values(), ignore_index=True)
            (out_dir / "submissoes_por_entrada.json").write_text(
                json.dumps(list(todas.submissao), ensure_ascii=False, indent=1), encoding="utf-8")
            todas.drop(columns=["submissao"]).to_csv(out_dir / "melhor_por_entrada.csv", index=False)
            md += ["### Melhor configuração para cada limite de potência (entrada / demanda)", "",
                   "Mesmo limite = mesma física; simulamos a entrada de menor kVA que comporta cada demanda. "
                   "Decidir com os custos de H4: ampliar vale se os perdidos/upgrades evitados pagam a obra da "
                   "entrada + a demanda contratada (A4/SE paga por kW; B3 não paga). Duas tabelas: sem e com "
                   "`evitar_ponta` (a troca é kWh na ponta × perdidos/upgrades).", ""]
            for ev, df_e in por_ent.items():
                cols_e = [c for c in dict.fromkeys(["entrada", "demanda", "limite_kw"] + cols) if c in df_e]
                md += [f"**evitar_ponta = {str(ev).lower()}**", "", _md(df_e[cols_e], 1), ""]
            md += ["Submissões em `submissoes_por_entrada.json`.", ""]
        if not incluir_nao_validadas:
            md += ["_Recomendações excluem `menor_soc` + `divisao=prioridade` (ainda diverge do juiz no teste 06); "
                   "use `--incluir-nao-validadas` para incluir._", ""]
        md += ["",
               "### Fronteira de Pareto (perdidos previstos × kW nominal)", "",
               _md(fr[["config", "pol_prioridade", "pol_divisao", "pol_evitar_ponta", "kw_nominal", "p_nao_atendidos",
                       "p_upgrades"]].head(15), 1), ""]

    md.append(f"_Tempo total: {time.time() - t0:.0f} s._")
    (out_dir / "relatorio.md").write_text("\n".join(md), encoding="utf-8")
    return out_dir / "relatorio.md"


def main() -> None:
    ap = argparse.ArgumentParser(prog="python3 -m ml.rodar")
    ap.add_argument("agencia", nargs="?")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--etapas", default=",".join(ETAPAS))
    ap.add_argument("--amostras", type=int, default=300)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--cenarios", type=int, default=0, help="semanas reamostradas para checar robustez dos top")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--entradas", choices=["auto", "existente"], default="auto",
                    help="auto: explora B3 maior e A4/SE com várias demandas; existente: só a atual")
    ap.add_argument("--incluir-nao-validadas", action="store_true",
                    help="inclui políticas que ainda divergem do juiz (menor_soc + divisao=prioridade)")
    a = ap.parse_args()
    cat_path = F.DADOS / "catalogo.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else None
    ags = sorted(p.name for p in F.DADOS.iterdir() if (p / "contratos_publicos.csv").exists()) if a.todas else [a.agencia]
    if not ags or ags == [None]:
        raise SystemExit("informe a agência ou --todas")
    sys.stdout.reconfigure(encoding="utf-8")
    for ag in ags:
        p = analisar(ag, tuple(a.etapas.split(",")), a.amostras, a.top, a.cenarios, a.workers, cat, a.entradas, a.incluir_nao_validadas)
        print(f"{ag}: {p}")


if __name__ == "__main__":
    main()
