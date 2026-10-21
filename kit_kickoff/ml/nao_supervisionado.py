"""Aprendizado não supervisionado sobre os dados de uma agência.

agrupar_modelos(cen)     KMeans nas features das CURVAS (AC, pico/média/queda DC, bateria)
                         -> classes de recarga; diz que carregador cada classe aproveita
agrupar_contratos(ct)    KMeans em duração/horário/km/categoria -> segmentos de cliente
agrupar_dias(dias)       KMeans no perfil horário (retiradas + kWh que chega) -> tipos de dia
anomalias(ct)            IsolationForest -> contratos fora do padrão (ex.: 40 dias de duração)

k é escolhido pelo coeficiente de silhueta; random_state fixo (resultado reprodutível).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .features import carregador_suficiente, tabela_modelos

FEATS_CURVA = ["ac_kw", "dc_pico_kw", "dc_medio_20_80", "dc_queda", "bateria_kwh", "kwh_km"]
FEATS_CONTRATO = ["log_dur_h", "hora_ret", "hora_dev", "km_devolucao", "rank", "devolve_na_abertura"]


def escolher_k(X: np.ndarray, ks) -> tuple:
    """(k, silhueta, modelo) com a maior silhueta entre os k candidatos válidos."""
    melhor = (None, -1.0, None)
    for k in ks:
        if k < 2 or k >= len(X):
            continue
        km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(X)
        if len(set(km.labels_)) < 2:
            continue
        s = silhouette_score(X, km.labels_)
        if s > melhor[1] + 1e-9:
            melhor = (k, float(s), km)
    return melhor


def _renomear_por(df: pd.DataFrame, col_cluster: str, col_ordem: str, nomes) -> pd.DataFrame:
    """Renumera clusters pela média de `col_ordem` (0 = menor) e dá nome legível."""
    ordem = df.groupby(col_cluster)[col_ordem].mean().sort_values().index
    mapa = {c: i for i, c in enumerate(ordem)}
    df[col_cluster] = df[col_cluster].map(mapa)
    n = len(ordem)
    df[col_cluster + "_nome"] = df[col_cluster].map(lambda i: nomes[i] if n == len(nomes) else f"grupo {i}")
    return df


def agrupar_modelos(cen, ks=range(2, 5)) -> tuple:
    """Classes de recarga dos modelos da agência. Retorna (tabela, info)."""
    tm = tabela_modelos(cen)
    X = StandardScaler().fit_transform(tm[FEATS_CURVA])
    k, sil, km = escolher_k(X, ks)
    tm["classe_recarga"] = km.labels_ if km is not None else 0
    pca = PCA(n_components=2, random_state=0).fit(X)
    tm[["pc1", "pc2"]] = pca.transform(X)
    tm = _renomear_por(tm, "classe_recarga", "dc_medio_20_80", [])
    medias = tm.groupby("classe_recarga")[["ac_kw", "dc_medio_20_80", "bateria_kwh"]].mean()
    tm["classe_recarga_nome"] = tm.classe_recarga.map(
        lambda c: f"AC~{medias.ac_kw[c]:.0f}kW DC~{medias.dc_medio_20_80[c]:.0f}kW bat~{medias.bateria_kwh[c]:.0f}kWh")
    tm["carregador_suficiente"] = [carregador_suficiente(cen, cen.modelos[m]) for m in tm.modelo]
    info = {"k": k, "silhueta": sil, "pca_variancia": pca.explained_variance_ratio_.round(3).tolist(),
            "pca_pesos_pc1": dict(zip(FEATS_CURVA, pca.components_[0].round(3)))}
    return tm, info


def energia_por_classe(tm: pd.DataFrame, sessoes: pd.DataFrame) -> pd.DataFrame:
    """Quanto da energia (kWh) de recarga da agência vem de cada classe de curva."""
    s = sessoes.merge(tm[["modelo", "classe_recarga_nome", "carregador_suficiente"]], on="modelo")
    out = s.groupby(["classe_recarga_nome", "carregador_suficiente"]).agg(
        sessoes=("kwh", "size"), kwh=("kwh", "sum")).reset_index()
    out["pct_kwh"] = 100 * out.kwh / out.kwh.sum()
    return out.sort_values("pct_kwh", ascending=False)


def _x_contratos(ct: pd.DataFrame) -> pd.DataFrame:
    d = ct.dropna(subset=["dur_h", "hora_dev", "km_devolucao"]).copy()
    d["log_dur_h"] = np.log1p(d.dur_h)
    return d


def agrupar_contratos(ct: pd.DataFrame, ks=range(2, 7)) -> tuple:
    d = _x_contratos(ct)
    X = StandardScaler().fit_transform(d[FEATS_CONTRATO])
    k, sil, km = escolher_k(X, ks)
    d["segmento"] = km.labels_
    d = _renomear_por(d, "segmento", "dur_h", [])
    agg = {"contratos": ("id", "size"), "dur_h_mediana": ("dur_h", "median"), "hora_ret_media": ("hora_ret", "mean"),
           "km_dev_medio": ("km_devolucao", "mean"), "rank_medio": ("rank", "mean"),
           "pct_devolve_abertura": ("devolve_na_abertura", "mean"), "kwh_esperado_medio": ("kwh_esperado", "mean")}
    if "kwh" in d:
        agg["kwh_real_medio"] = ("kwh", "mean")
    perfil = d.groupby("segmento").agg(**agg).reset_index()
    return d, perfil, {"k": k, "silhueta": sil}


def agrupar_dias(dias: pd.DataFrame, ks=range(2, 6)) -> tuple:
    cols = [c for c in dias.columns if c.startswith(("ret_h", "kwh_h"))]
    X = StandardScaler().fit_transform(dias[cols])
    k, sil, km = escolher_k(X, ks)
    d = dias.copy()
    d["tipo_dia"] = km.labels_
    d = _renomear_por(d, "tipo_dia", "retiradas", [])
    nomes_dia = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")
    perfil = d.groupby("tipo_dia").agg(
        dias=("dia", "size"), retiradas_media=("retiradas", "mean"), devolucoes_media=("devolucoes", "mean"),
        kwh_esperado_medio=("kwh_esperado", "mean"),
        dias_da_semana=("dia_sem", lambda s: ", ".join(f"{nomes_dia[i]}×{n}" for i, n in s.value_counts().sort_index().items())),
    ).reset_index()
    return d, perfil, {"k": k, "silhueta": sil}


def anomalias(ct: pd.DataFrame, contaminacao: float = 0.03) -> pd.DataFrame:
    d = _x_contratos(ct)
    iso = IsolationForest(contamination=contaminacao, random_state=0).fit(d[FEATS_CONTRATO])
    d["anomalia"] = iso.predict(d[FEATS_CONTRATO]) == -1
    d["score_anomalia"] = -iso.score_samples(d[FEATS_CONTRATO])
    return d[d.anomalia].sort_values("score_anomalia", ascending=False)
