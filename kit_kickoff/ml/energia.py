"""Previsão de energia de recarga.

Rótulos vêm do motor (validado contra o juiz): kWh real de cada sessão até 80%.

avaliar_contratos(cen)  kWh por devolução a partir das features do contrato
                        modelos: física (média da frota da categoria), Ridge, GBM, GBM só com dados brutos
                        validação: deixa uma semana inteira de fora (GroupKFold por semana)
avaliar_dias(cen)       kWh que chega por dia; mesma validação por semana
perfil_semanal(cen)     kWh médio (e desvio) que chega por dia da semana × hora -> previsão das ocultas
potencia_livre(cen)     potência de 15 min que a agência PEDIRIA sem limite de entrada (só vagas e curvas)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_selection import mutual_info_regression
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from kickoff import medicao, tempo, validar

from . import features as F

FEATS_CONTRATO = ["rank", "km_devolucao", "dur_h", "hora_ret", "hora_dev", "dia_sem_ret", "dia_sem_dev",
                  "devolve_na_abertura", "autonomia_min_km", "soc_esperado", "kwh_esperado"]
FEATS_BRUTAS = [f for f in FEATS_CONTRATO if f not in ("soc_esperado", "kwh_esperado")]


def _gbm():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                         min_samples_leaf=10, random_state=0)


def _ridge():
    return make_pipeline(StandardScaler(), Ridge(alpha=1.0))


def _cv(df, feats, alvo, grupos, fabrica, n_imp=0):
    """Validação deixando um grupo (semana) de fora. Devolve (previsões, importâncias médias)."""
    pred = np.full(len(df), np.nan)
    imps = []
    gkf = GroupKFold(n_splits=min(len(set(grupos)), 4))
    for tr, te in gkf.split(df, df[alvo], grupos):
        m = fabrica().fit(df.iloc[tr][feats], df.iloc[tr][alvo])
        pred[te] = m.predict(df.iloc[te][feats])
        if n_imp:
            pi = permutation_importance(m, df.iloc[te][feats], df.iloc[te][alvo], n_repeats=n_imp,
                                        random_state=0, scoring="neg_mean_absolute_error")
            imps.append(pi.importances_mean)
    imp = pd.Series(np.mean(imps, axis=0), index=feats).sort_values(ascending=False) if imps else None
    return pred, imp


def _metricas(y, p) -> dict:
    return {"MAE": float(mean_absolute_error(y, p)), "R2": float(r2_score(y, p)),
            "erro_total_pct": float(100 * (p.sum() - y.sum()) / y.sum())}


def avaliar_contratos(cen, res=None) -> dict:
    df = F.contratos_rotulados(cen, res).dropna(subset=FEATS_CONTRATO + ["kwh"]).reset_index(drop=True)
    g = df.semana.values
    linhas = {"física (frota da categoria)": _metricas(df.kwh, df.kwh_esperado.values)}
    p, _ = _cv(df, FEATS_CONTRATO, "kwh", g, _ridge)
    linhas["Ridge"] = _metricas(df.kwh, p)
    p, imp = _cv(df, FEATS_CONTRATO, "kwh", g, _gbm, n_imp=5)
    linhas["GBM (física + dados)"] = _metricas(df.kwh, p)
    p, imp_b = _cv(df, FEATS_BRUTAS, "kwh", g, _gbm, n_imp=5)
    linhas["GBM (só dados brutos)"] = _metricas(df.kwh, p)
    mi = pd.Series(mutual_info_regression(df[FEATS_CONTRATO], df.kwh, random_state=0), index=FEATS_CONTRATO)
    return {"n": len(df), "metricas": pd.DataFrame(linhas).T,
            "importancia_gbm": imp, "importancia_gbm_bruto": imp_b,
            "informacao_mutua": mi.sort_values(ascending=False), "dados": df}


def _dias_rotulados(cen, res) -> pd.DataFrame:
    dias = F.tabela_dias(cen)
    s = F.sessoes_energia(cen, res)
    s["dia"] = (s.t // tempo.DIA).astype(int)
    real = s.groupby("dia").kwh.sum()
    t0 = s[s.origem != "devolucao"].groupby("dia").kwh.sum()
    dias["kwh_real"] = dias.dia.map(real).fillna(0.0)
    dias["kwh_t0_conhecido"] = dias.dia.map(t0).fillna(0.0)  # frota em T0: energia já conhecida
    dias["kwh_fisica"] = dias.kwh_esperado + dias.kwh_t0_conhecido
    dias["semana"] = ((dias.dia * tempo.DIA - tempo.T0) // (7 * tempo.DIA)).clip(lower=0).astype(int)
    return dias


def avaliar_dias(cen, res=None) -> dict:
    res = res or F.simular(cen)
    d = _dias_rotulados(cen, res)
    feats = ["dia_sem", "horas_abertas", "retiradas", "devolucoes", "kwh_esperado", "kwh_t0_conhecido"] + \
            [c for c in d.columns if c.startswith("ret_rank")]
    linhas = {"física (esperado + T0)": _metricas(d.kwh_real, d.kwh_fisica.values)}
    p, _ = _cv(d, feats, "kwh_real", d.semana.values, _ridge)
    linhas["Ridge"] = _metricas(d.kwh_real, p)
    p, imp = _cv(d, feats, "kwh_real", d.semana.values, _gbm, n_imp=5)
    linhas["GBM"] = _metricas(d.kwh_real, p)
    # o que dá para prever SEM saber os contratos (só calendário): é o cenário das semanas ocultas
    cal = ["dia_sem", "horas_abertas"]
    p, _ = _cv(d, cal, "kwh_real", d.semana.values, _gbm)
    linhas["GBM só calendário"] = _metricas(d.kwh_real, p)
    return {"n": len(d), "metricas": pd.DataFrame(linhas).T, "importancia_gbm": imp, "dados": d}


def perfil_semanal(cen, res=None) -> pd.DataFrame:
    """kWh que chega por dia da semana × hora (média e desvio entre as semanas públicas)."""
    res = res or F.simular(cen)
    s = F.sessoes_energia(cen, res)
    s = s[(s.origem == "devolucao") & (s.t >= tempo.JANELA_PUBLICA[0]) & (s.t < tempo.JANELA_PUBLICA[1])].copy()
    s["semana"] = ((s.t - tempo.T0) // (7 * tempo.DIA)).astype(int)
    s["dia_sem"] = [tempo.dia_semana(t) for t in s.t]
    s["hora"] = ((s.t % tempo.DIA) // 60).astype(int)
    tab = s.groupby(["semana", "dia_sem", "hora"]).kwh.sum().unstack(["dia_sem", "hora"], fill_value=0.0)
    out = pd.DataFrame({"kwh_media": tab.mean(), "kwh_desvio": tab.std(ddof=0)}).reset_index()
    return out


def potencia_livre(cen) -> dict:
    """Potência pedida sem limite de entrada: carregadores mais rápidos em todas as vagas e a maior
    entrada do catálogo. Mostra até onde ampliar a entrada faria diferença."""
    rapido = max(cen.carregadores.values(), key=lambda c: (c.potencia_kw / c.saidas, -c.saidas))
    n = cen.agencia.vagas // rapido.saidas
    car = {rapido.id: n} if n else {}
    resto = cen.agencia.vagas - n * rapido.saidas
    if resto:
        um = max((c for c in cen.carregadores.values() if c.saidas == 1), key=lambda c: c.potencia_kw)
        car[um.id] = resto
    ent = max(cen.entradas.values(), key=lambda e: e.kw_util)
    sub = validar.normalizar({"agencia": cen.agencia.nome, "carregadores": car, "entrada": ent.id}, cen)
    res = F.simular(cen, sub)
    ini, fim = tempo.JANELA_PUBLICA
    serie = np.array(medicao.series(res.bins, res.trace, res.retiradas, res.nao_atendidos, ini, fim)["potencia_kw"])
    ativa = serie[serie > 0]
    q = {f"P{p}": float(np.percentile(ativa, p)) for p in (50, 90, 95, 99)} if len(ativa) else {}
    m = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, ini, fim)
    return {"carregadores": car, "entrada": ent.id, "pico_kw": float(serie.max()), **q,
            "horas_com_carga_pct": float(100 * len(ativa) / len(serie)),
            "nao_atendidos_sem_limite": m["nao_atendidos"], "upgrades_sem_limite": m["upgrades"],
            "serie": serie}
