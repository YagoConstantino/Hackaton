"""Escolha de carregadores: modelo substituto (surrogate) treinado em simulações do motor.

combos(cen)                 todas as combinações válidas de carregadores (Σ saídas ≤ vagas)
gerar_dataset(cen, n)       amostra n (combinação, política, entrada) e simula com o motor
treinar(df)                 um GBM por métrica (não_atendidos, upgrades, energia na ponta, pico)
prever_todos(cen, modelos)  prevê TODAS as combinações × políticas sem simular
fronteira(pred)             fronteira de Pareto: menos perdas por kW nominal instalado (proxy de custo)
recomendar(...)             melhores candidatos pelo surrogate, confirmados no motor (opcional:
                            em semanas reamostradas, para robustez)

Antes de H4 os custos são desconhecidos: o custo é aproximado por kW nominal e nº de carregadores.
Depois de H4, passe o catálogo (dados/catalogo.json) e a ordenação usa a nota estimada.
"""
from __future__ import annotations

import itertools
import os
import random
from multiprocessing import get_context

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold

from kickoff import medicao, nota, tempo, validar

from . import features as F
from .sintetico import reamostrar_semanas

ALVOS = ["nao_atendidos", "upgrades", "energia_ponta_kwh", "pico_kw"]
POLITICAS = [{"prioridade": p, "divisao": d, "evitar_ponta": e}
             for p in validar.MENU["prioridade"] for d in validar.MENU["divisao"] for e in (False, True)]
# menor_soc + divisao=prioridade ainda diverge do juiz (validacao/06): fora das recomendações por padrão
NAO_VALIDADAS = [{"prioridade": "menor_soc", "divisao": "prioridade"}]
POLITICAS_VALIDADAS = [p for p in POLITICAS
                       if not any(all(p[k] == v for k, v in nv.items()) for nv in NAO_VALIDADAS)]


# ---------------------------------------------------------------- espaço de busca

def combos(cen) -> list:
    cars = sorted(cen.carregadores.values(), key=lambda c: c.id)
    v = cen.agencia.vagas
    out = []
    for q in itertools.product(*[range(v // c.saidas + 1) for c in cars]):
        s = sum(n * c.saidas for n, c in zip(q, cars))
        if 1 <= s <= v:
            out.append({c.id: n for n, c in zip(q, cars) if n})
    return out


def entradas_validas(cen, demandas=(None,)) -> list:
    """[(entrada, demanda)] que a agência pode submeter. `demandas` vale só para A4/SE."""
    ex = cen.entradas[cen.agencia.entrada_existente]
    out = []
    for e in sorted(cen.entradas.values(), key=lambda e: e.kw_util):
        if e.id != ex.id and (e.kva < validar.B3_KVA or e.kw_util < ex.kw_util):
            continue
        if e.kva <= validar.B3_KVA:
            out.append((e.id, None))
        else:
            for d in demandas:
                if d is None or validar.DEMANDA_MIN_KW <= validar.arredondar_demanda(d) <= validar.teto_demanda(e):
                    out.append((e.id, d))
    return out


def entradas_auto(cen, demandas=(60, 80, 100, 130, 160, 200, 270), kw_max=270.0) -> list:
    """Opções de limite de potência a explorar: a entrada existente, o B3 maior (se puder subir; B3 não
    paga demanda) e, para cada demanda contratada, a MENOR entrada A4/SE que a comporta.
    Mesmo limite = mesma física; só o custo muda, então simulamos só a opção de menor kVA."""
    ex = cen.entradas[cen.agencia.entrada_existente]
    out = [(ex.id, None)]
    b3 = [e for e in cen.entradas.values()
          if e.id != ex.id and e.kva <= validar.B3_KVA and e.kva >= validar.B3_KVA and e.kw_util > ex.kw_util]
    out += [(e.id, None) for e in sorted(b3, key=lambda e: e.kva)]
    a4 = sorted((e for e in cen.entradas.values()
                 if e.kva > validar.B3_KVA and ex.kw_util <= e.kw_util <= kw_max + 1e-9), key=lambda e: e.kva)
    for d in demandas:
        if d <= ex.kw_util:
            continue
        e = next((e for e in a4 if validar.DEMANDA_MIN_KW <= d <= validar.teto_demanda(e)), None)
        if e is not None:
            out.append((e.id, d))
    return out


def melhor_por_entrada(cen, modelos, entradas, politicas=None, cenarios=0, workers=None) -> pd.DataFrame:
    """Para cada opção de entrada/demanda, a melhor configuração (confirmada no motor): a tabela para
    decidir se vale ampliar (perdidos evitados × custo da obra e da demanda, que saem em H4)."""
    linhas, vencedores = [], []
    chave = ["nao_atendidos", "upgrades", "kw_nominal", "energia_ponta_kwh"]
    lim = {e: validar.limite_kw(validar.normalizar(_sub(cen, {next(iter(cen.carregadores)): 1}, {}, *e), cen), cen)
           for e in entradas}
    for ent in sorted(entradas, key=lambda e: lim[e]):
        r = recomendar(cen, modelos, top=3, politicas=politicas, entradas=[ent], cenarios=cenarios, workers=workers)
        # leva os vencedores dos limites menores: com mais limite eles rendem pelo menos o mesmo
        extra = [(_de_texto(w.config), {"prioridade": w.pol_prioridade, "divisao": w.pol_divisao,
                                        "evitar_ponta": bool(w.pol_evitar_ponta)}) for w in vencedores]
        extra = [(c, p) for c, p in extra if not ((r.config == _texto(c)) & (r.pol_prioridade == p["prioridade"]) &
                                                  (r.pol_divisao == p["divisao"]) & (r.pol_evitar_ponta == p["evitar_ponta"])).any()]
        if extra:
            reais = _mapear(cen, [(c, p, *ent, None) for c, p in extra], workers)
            add = pd.DataFrame([{"config": _texto(c), "entrada": ent[0], "demanda": ent[1], "pol_prioridade": p["prioridade"],
                                 "pol_divisao": p["divisao"], "pol_evitar_ponta": p["evitar_ponta"],
                                 "kw_nominal": features_config(cen, c, p, *ent)["kw_nominal"],
                                 **{k: m[k] for k in ("nao_atendidos", "upgrades", "energia_ponta_kwh", "pico_kw")},
                                 "submissao": _sub(cen, c, p, *ent)} for (c, p), m in zip(extra, reais)])
            if cenarios:
                rob = _mapear(cen, [(c, p, *ent, s) for c, p in extra for s in range(1, cenarios + 1)], workers)
                perdas = np.array([m["nao_atendidos"] for m in rob]).reshape(len(extra), cenarios)
                add["perdidos_media_reamostr"], add["perdidos_pior_reamostr"] = perdas.mean(axis=1), perdas.max(axis=1)
            r = pd.concat([r, add], ignore_index=True).sort_values(chave).reset_index(drop=True)
        linhas.append(r.iloc[0])
        vencedores.append(r.iloc[0])
    out = pd.DataFrame(linhas).reset_index(drop=True)
    out["limite_kw"] = [validar.limite_kw(validar.normalizar(s, cen), cen) for s in out.submissao]
    return out


def _sub(cen, car, pol, entrada, demanda):
    s = {"agencia": cen.agencia.nome, "carregadores": car, "entrada": entrada, "politica": pol}
    if demanda is not None:
        s["demanda_contratada_kw"] = demanda
    return s


def features_config(cen, car, pol, entrada, demanda) -> dict:
    cs = cen.carregadores
    sn = validar.normalizar(_sub(cen, car, pol, entrada, demanda), cen)
    limite = validar.limite_kw(sn, cen)
    ac = [(cs[k], n) for k, n in car.items() if cs[k].tipo == "AC"]
    dc = [(cs[k], n) for k, n in car.items() if cs[k].tipo == "DC"]
    kw_ac = sum(c.potencia_kw * n for c, n in ac)
    kw_dc = sum(c.potencia_kw * n for c, n in dc)
    r = {
        "saidas_ac": sum(c.saidas * n for c, n in ac), "saidas_dc": sum(c.saidas * n for c, n in dc),
        "kw_ac": kw_ac, "kw_dc": kw_dc, "kw_nominal": kw_ac + kw_dc,
        "kw_dc_saida_max": max([c.potencia_kw / c.saidas for c, _ in dc], default=0.0),
        "kw_dc_saida_cheia_min": min([c.potencia_kw / c.saidas for c, _ in dc], default=0.0),
        "n_carregadores": sum(car.values()), "n_2saidas": sum(n for k, n in car.items() if cs[k].saidas > 1),
        "limite_kw": limite, "kw_nominal_sobre_limite": (kw_ac + kw_dc) / limite,
        "demanda_kw": sn["demanda_contratada_kw"] or 0.0,
        "prio_menor_soc": int(pol["prioridade"] == "menor_soc"), "prio_chegada": int(pol["prioridade"] == "chegada"),
        "prio_proxima": int(pol["prioridade"] == "proxima_retirada"),
        "div_prioridade": int(pol["divisao"] == "prioridade"), "evitar_ponta": int(pol["evitar_ponta"]),
    }
    r["saidas"] = r["saidas_ac"] + r["saidas_dc"]
    r["saidas_sobre_vagas"] = r["saidas"] / cen.agencia.vagas
    for k in sorted(cs):
        r[f"qtd_{k}"] = car.get(k, 0)
    return r


# ---------------------------------------------------------------- simulação (paralela)

_CEN = None


def _init(agencia, dados_dir):
    global _CEN
    _CEN = F.carregar(agencia, dados_dir)


def _rodar(args):
    car, pol, entrada, demanda, seed_cen = args
    cen = _CEN if seed_cen is None else reamostrar_semanas(_CEN, seed_cen)
    return simular_config(cen, car, pol, entrada, demanda)


def simular_config(cen, car, pol, entrada, demanda=None) -> dict:
    sn = validar.normalizar(_sub(cen, car, pol, entrada, demanda), cen)
    res = F.simular(cen, sn)
    m = medicao.metricas(res.retiradas, res.nao_atendidos, res.bins, *tempo.JANELA_PUBLICA)
    m["demanda_contratada_kw"] = sn["demanda_contratada_kw"] or 0.0
    m["violacoes"] = len(res.violacoes)
    return m


def _mapear(cen, tarefas, workers):
    workers = workers or os.cpu_count() or 1
    if workers <= 1 or len(tarefas) < 8:
        global _CEN
        _CEN = cen
        return [_rodar(t) for t in tarefas]
    ctx = get_context("fork") if hasattr(os, "fork") else get_context()
    dados_dir = F.DADOS
    with ctx.Pool(workers, initializer=_init, initargs=(cen.agencia.nome, dados_dir)) as pool:
        return pool.map(_rodar, tarefas, chunksize=4)


def amostrar(cen, n, seed=0, politicas=None, entradas=None) -> list:
    """n tarefas: nº de saídas sorteado uniforme (para cobrir configurações pequenas e grandes)."""
    rnd = random.Random(seed)
    por_saidas: dict = {}
    for c in combos(cen):
        por_saidas.setdefault(sum(cen.carregadores[k].saidas * q for k, q in c.items()), []).append(c)
    pols = politicas or POLITICAS
    ents = entradas or [(cen.agencia.entrada_existente, None)]
    chaves = sorted(por_saidas)
    return [(rnd.choice(por_saidas[rnd.choice(chaves)]), rnd.choice(pols), *rnd.choice(ents), None) for _ in range(n)]


def gerar_dataset(cen, n=300, seed=0, politicas=None, entradas=None, workers=None) -> pd.DataFrame:
    tarefas = amostrar(cen, n, seed, politicas, entradas)
    mets = _mapear(cen, tarefas, workers)
    linhas = []
    for (car, pol, ent, dem, _), m in zip(tarefas, mets):
        linhas.append({"config": _texto(car), "entrada": ent, "demanda": dem, **{f"pol_{k}": v for k, v in pol.items()},
                       **features_config(cen, car, pol, ent, dem), **{f"y_{k}": m[k] for k in ALVOS},
                       "y_certos": m["certos"], "y_energia_kwh": m["energia_kwh"]})
    return pd.DataFrame(linhas).drop_duplicates(subset=["config", "entrada", "demanda", "pol_prioridade",
                                                        "pol_divisao", "pol_evitar_ponta"]).reset_index(drop=True)


def _texto(car) -> str:
    return " + ".join(f"{n}×{k}" for k, n in sorted(car.items()))


def _de_texto(s: str) -> dict:
    return {k: int(n) for n, k in (p.split("×") for p in s.split(" + "))}


# ---------------------------------------------------------------- surrogate

def colunas_x(df) -> list:
    nao = {"config", "entrada", "demanda"}
    return [c for c in df.columns if not c.startswith(("y_", "pol_")) and c not in nao]


def treinar(df: pd.DataFrame, alvos=ALVOS, n_imp: int = 5) -> dict:
    X = df[colunas_x(df)]
    out = {}
    for a in alvos:
        y = df[f"y_{a}"]
        pred = np.zeros(len(df))
        for tr, te in KFold(5, shuffle=True, random_state=0).split(X):
            m = _gbm().fit(X.iloc[tr], y.iloc[tr])
            pred[te] = m.predict(X.iloc[te])
        modelo = _gbm().fit(X, y)
        imp = None
        if n_imp:
            corte = int(len(df) * 0.75)
            mi = _gbm().fit(X.iloc[:corte], y.iloc[:corte])
            pi = permutation_importance(mi, X.iloc[corte:], y.iloc[corte:], n_repeats=n_imp, random_state=0,
                                        scoring="neg_mean_absolute_error")
            imp = pd.Series(pi.importances_mean, index=X.columns).sort_values(ascending=False)
        out[a] = {"modelo": modelo, "MAE_cv": float(mean_absolute_error(y, pred)),
                  "R2_cv": float(r2_score(y, pred)) if y.std() > 0 else float("nan"),
                  "media_y": float(y.mean()), "importancia": imp}
    return out


def _gbm():
    return HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
                                         min_samples_leaf=5, random_state=0)


def prever_todos(cen, modelos, politicas=None, entradas=None) -> pd.DataFrame:
    linhas = []
    for car in combos(cen):
        for pol in politicas or POLITICAS:
            for ent, dem in entradas or [(cen.agencia.entrada_existente, None)]:
                linhas.append({"config": _texto(car), "entrada": ent, "demanda": dem,
                               **{f"pol_{k}": v for k, v in pol.items()}, **features_config(cen, car, pol, ent, dem)})
    df = pd.DataFrame(linhas)
    X = df[[c for c in colunas_x(df)]]
    for a, info in modelos.items():
        df[f"p_{a}"] = np.clip(info["modelo"].predict(X[info["modelo"].feature_names_in_]), 0, None)
    return df


def fronteira(pred: pd.DataFrame, col_perda="p_nao_atendidos", col_custo="kw_nominal") -> pd.DataFrame:
    """Configurações não dominadas: nenhuma outra tem custo ≤ e perda < ao mesmo tempo."""
    d = pred.sort_values([col_custo, col_perda]).reset_index(drop=True)
    melhor, keep = np.inf, []
    for i, r in d.iterrows():
        if r[col_perda] < melhor - 1e-9:
            keep.append(i)
            melhor = r[col_perda]
    return d.loc[keep]


# ---------------------------------------------------------------- recomendação

def _custos(cat):
    car = {c["id"]: c["custo"] for c in (cat or {}).get("carregadores", []) if "custo" in c}
    ent = {e["id"]: e["custo"] for e in (cat or {}).get("entradas", []) if "custo" in e}
    return car, ent


def nota_estimada(cen, cat, car, entrada, metr) -> float | None:
    pesos = (cat or {}).get("pesos", {}).get(cen.agencia.nome)
    cc, ce = _custos(cat)
    if not pesos or not cc:
        return None
    obra = sum(cc[k] * n for k, n in car.items()) + (0 if entrada == cen.agencia.entrada_existente else ce.get(entrada, 0))
    m = {"certos": metr["certos"], "upgrades": metr["upgrades"], "nao_atendidos": metr["nao_atendidos"],
         "demanda_contratada_kw": metr.get("demanda_contratada_kw", 0.0),
         "energia_ponta_kwh": metr["energia_ponta_kwh"], "custo_infra": obra}
    return nota.pontuar(m, pesos)["nota"]


def recomendar(cen, modelos, top=10, cat=None, politicas=None, entradas=None, cenarios=0, workers=None) -> pd.DataFrame:
    """Ordena tudo pelo surrogate e confirma os `top` no motor. Com `cenarios` > 0, confirma também
    em semanas reamostradas e reporta média e pior caso de clientes perdidos."""
    pred = prever_todos(cen, modelos, politicas, entradas)
    n_contr = len(cen.contratos)
    if cat and _custos(cat)[0] and (cat.get("pesos") or {}).get(cen.agencia.nome):
        pesos = cat["pesos"][cen.agencia.nome]
        cc, ce = _custos(cat)
        obra = pred.config.map(lambda s: sum(cc[k] * n for k, n in _de_texto(s).items())) + \
            pred.entrada.map(lambda e: 0 if e == cen.agencia.entrada_existente else ce.get(e, 0))
        up, nao = pred.p_upgrades, pred.p_nao_atendidos
        # mesma convenção de nota.pontuar (kit): nota = Σ peso × métrica, com o sinal no peso
        pred["nota_prevista"] = (pesos["certo"] * (n_contr - nao - up) + pesos["upgrade"] * up
                                 + pesos["nao_atendido"] * nao + pesos["demanda_contratada"] * pred.demanda_kw
                                 + pesos["energia_ponta_kwh"] * pred.p_energia_ponta_kwh
                                 + pesos["infraestrutura"] * obra)
        pred["ordem"] = -pred.nota_prevista
        cand = pred.sort_values("ordem").head(top)
    else:
        # Neblina: menos perdas, depois menos upgrades, depois menos kW instalado, menos energia na ponta
        pred["_perda"] = pred.p_nao_atendidos.round(0)
        pred["_up"] = pred.p_upgrades.round(0)
        cand = pred.sort_values(["_perda", "_up", "kw_nominal", "n_carregadores", "p_energia_ponta_kwh"]).head(top)
    tarefas = [(_de_texto(r.config), {"prioridade": r.pol_prioridade, "divisao": r.pol_divisao,
                                      "evitar_ponta": bool(r.pol_evitar_ponta)}, r.entrada,
                None if pd.isna(r.demanda) else r.demanda, None) for r in cand.itertuples()]
    reais = _mapear(cen, tarefas, workers)
    out = cand[["config", "entrada", "demanda", "pol_prioridade", "pol_divisao", "pol_evitar_ponta", "kw_nominal",
                "p_nao_atendidos", "p_upgrades", "p_energia_ponta_kwh"]].copy().reset_index(drop=True)
    for k in ("nao_atendidos", "upgrades", "energia_ponta_kwh", "pico_kw"):
        out[k] = [m[k] for m in reais]
    if cat:
        out["nota_estimada"] = [nota_estimada(cen, cat, t[0], t[2], m) for t, m in zip(tarefas, reais)]
    if cenarios:
        rob = _mapear(cen, [t[:4] + (s,) for t in tarefas for s in range(1, cenarios + 1)], workers)
        perdas = np.array([m["nao_atendidos"] for m in rob]).reshape(len(tarefas), cenarios)
        out["perdidos_media_reamostr"] = perdas.mean(axis=1)
        out["perdidos_pior_reamostr"] = perdas.max(axis=1)
    out["submissao"] = [_sub(cen, *t[:4]) for t in tarefas]
    # reordena pelos números REAIS do motor (a previsão só serviu para escolher quem simular)
    if cat and "nota_estimada" in out and out.nota_estimada.notna().all():
        return out.sort_values("nota_estimada", ascending=False).reset_index(drop=True)
    return out.sort_values(["nao_atendidos", "upgrades", "kw_nominal", "energia_ponta_kwh"]).reset_index(drop=True)
