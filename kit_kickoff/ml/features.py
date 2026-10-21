"""Features por agência, lidas de dados/<Agencia>/ (nada fixo por agência).

Tabelas:
  tabela_modelos(cen)      um modelo de carro por linha: bateria, curvas, tempos de recarga por carregador
  tabela_contratos(cen)    um contrato por linha: horário, duração, km, energia esperada pela física
  sessoes_energia(cen,res) uma sessão de recarga por linha (rótulo real, vindo do motor)
  tabela_dias(cen)         um dia por linha: retiradas/devoluções/energia esperada por hora
  ficha_agencia(cen)       resumo da agência (vagas, horário, folga, pressão...)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, motor, tempo, validar  # noqa: E402

DADOS = RAIZ / "dados"
ALVO = validar.SOC_ALVO
DIA = tempo.DIA


def carregar(agencia: str, dados_dir: Path = DADOS):
    return dados.carregar(Path(dados_dir), agencia)


# ---------------------------------------------------------------- curvas e modelos

def tempo_recarga(modelo, s0: float, s1: float, cap_kw: float, tipo: str) -> float:
    """Minutos de s0% a s1% com no máximo cap_kw, pela curva em degraus (mesma regra do juiz)."""
    curva = modelo.curva_ac if tipo == "AC" else modelo.curva_dc
    t, s = 0.0, s0
    while s < s1 - 1e-9:
        i = min(19, int(s / 5 + 1e-9))
        lim = min(s1, (i + 1) * 5.0)
        p = min(cap_kw, curva[i])
        if p <= 0:
            return math.inf
        t += (lim - s) / 100.0 * modelo.bateria_kwh / p * 60.0
        s = lim
    return t


def _por_saida(car) -> float:
    """kW por saída quando todas as saídas estão ocupadas."""
    return car.potencia_kw / car.saidas


def tabela_modelos(cen) -> pd.DataFrame:
    """Um modelo por linha, com as features de curva e o tempo 20→80% em cada carregador do catálogo."""
    frota = pd.Series([v.modelo for v in cen.veiculos]).value_counts()
    linhas = []
    for m in cen.modelos.values():
        dc = np.array(m.curva_dc[:16])  # degraus de 0% a 80%
        ac = np.array(m.curva_ac[:16])
        r = {
            "modelo": m.modelo, "categoria": m.categoria, "rank": m.rank,
            "bateria_kwh": m.bateria_kwh, "autonomia_km": m.autonomia_km,
            "kwh_km": m.bateria_kwh / m.autonomia_km,
            "ac_kw": float(ac.max()), "dc_pico_kw": float(dc.max()),
            "dc_medio_20_80": float(dc[4:16].mean()), "dc_75_80": float(dc[15]),
            "dc_queda": float(dc[15] / dc.max()),  # quanto a curva cai até 80%
            "frota_n": int(frota.get(m.modelo, 0)),
        }
        for c in sorted(cen.carregadores.values(), key=lambda c: c.id):
            r[f"min_20_80_{c.id}"] = tempo_recarga(m, 20, 80, c.potencia_kw, c.tipo)
            if c.saidas > 1:
                r[f"min_20_80_{c.id}_cheio"] = tempo_recarga(m, 20, 80, _por_saida(c), c.tipo)
        linhas.append(r)
    return pd.DataFrame(linhas).sort_values(["rank", "modelo"]).reset_index(drop=True)


def carregador_suficiente(cen, modelo, tolerancia: float = 1.10) -> str:
    """Carregador de menor potência nominal que recarrega o modelo 20→80% em até `tolerancia` × o
    tempo do mais rápido (sozinho, sem limite). Mostra se DC rápido serve para aquele carro."""
    tempos = {c.id: tempo_recarga(modelo, 20, 80, c.potencia_kw, c.tipo) for c in cen.carregadores.values()}
    melhor = min(tempos.values())
    ok = [c for c in cen.carregadores.values() if tempos[c.id] <= melhor * tolerancia]
    return min(ok, key=lambda c: (c.potencia_kw, c.id)).id


# ---------------------------------------------------------------- horário

def _abertura_do_dia(cen, t: float):
    j = cen.agencia.horario[tempo.dia_semana(t)]
    return None if j is None else j[0]


def horas_abertas_semana(cen) -> float:
    return sum((j[1] - j[0]) / 60 for j in cen.agencia.horario if j is not None)


# ---------------------------------------------------------------- contratos

def mix_frota(cen) -> dict:
    """{rank: [(modelo, fração)]} da frota em T0: a chance de cada modelo atender cada categoria."""
    out: dict = {}
    for r in sorted(set(cen.categorias.values())):
        ms = pd.Series([v.modelo for v in cen.veiculos if v.rank == r]).value_counts(normalize=True)
        out[r] = [(cen.modelos[k], float(p)) for k, p in ms.items()]
    return out


def energia_esperada(km: float, rank: int, mix: dict) -> tuple:
    """(SOC esperado na volta, kWh esperado para voltar a 80%) pela média da frota da categoria."""
    ms = mix.get(rank) or []
    if not ms:
        return math.nan, math.nan
    soc = sum(p * min(ALVO, km / m.autonomia_km * 100) for m, p in ms)
    kwh = sum(p * max(0.0, ALVO - min(ALVO, km / m.autonomia_km * 100)) / 100 * m.bateria_kwh for m, p in ms)
    return soc, kwh


def tabela_contratos(cen) -> pd.DataFrame:
    mix = mix_frota(cen)
    linhas = []
    for c in cen.contratos:
        dev = c.devolucao_t
        ab = _abertura_do_dia(cen, dev) if dev is not None else None
        minuto_dev = dev % DIA if dev is not None else None
        soc_e, kwh_e = energia_esperada(c.km_devolucao or 0.0, c.rank, mix) if dev is not None else (math.nan, math.nan)
        linhas.append({
            "id": c.id, "categoria": c.categoria, "rank": c.rank,
            "retirada_t": c.retirada_t, "devolucao_t": dev,
            "semana": int((c.retirada_t - tempo.T0) // (7 * DIA)) + 1,
            "dia_sem_ret": tempo.dia_semana(c.retirada_t), "hora_ret": (c.retirada_t % DIA) / 60,
            "dia_sem_dev": tempo.dia_semana(dev) if dev is not None else -1,
            "hora_dev": minuto_dev / 60 if dev is not None else math.nan,
            "dur_h": (dev - c.retirada_t) / 60 if dev is not None else math.nan,
            "km_devolucao": c.km_devolucao, "autonomia_min_km": c.autonomia_min_retirada_km,
            "devolve_na_abertura": int(ab is not None and 0 <= minuto_dev - ab <= 30),
            "soc_esperado": soc_e, "kwh_esperado": kwh_e,
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- rótulos de energia (motor)

def sub_padrao(cen) -> dict:
    """Submissão de referência para gerar rótulos: entrada existente, máximo de saídas DC-30 (ou o
    carregador DC de menor potência), política padrão. Só serve para saber qual carro atende cada
    contrato; a energia de cada sessão quase não depende da infraestrutura."""
    dc = sorted((c for c in cen.carregadores.values() if c.tipo == "DC"), key=lambda c: (c.potencia_kw, c.id))
    car = dc[0] if dc else min(cen.carregadores.values(), key=lambda c: c.potencia_kw)
    n = max(1, cen.agencia.vagas // car.saidas)
    sub = {"agencia": cen.agencia.nome, "carregadores": {car.id: n}, "entrada": cen.agencia.entrada_existente}
    return validar.normalizar(sub, cen)


def simular(cen, sub_norm=None, eventos=()):
    return motor.simular(cen, sub_norm or sub_padrao(cen), eventos)


def sessoes_energia(cen, res) -> pd.DataFrame:
    """Uma linha por chegada ao pátio abaixo de 80% (T0 e devoluções), com o kWh real até 80%.
    A soma dos kWh fecha com a energia total medida pelo motor (teste de consistência)."""
    contratos = {c.id: c for c in cen.contratos}
    linhas = []
    for v in cen.veiculos:
        if v.situacao == "em_contrato":
            soc, t, origem = v.soc_devolucao, max(v.devolucao_t, tempo.T0), "t0_em_contrato"
        else:
            soc, t, origem = v.soc, tempo.T0, "t0_estoque"
        m = cen.modelos[v.modelo]
        linhas.append({"contrato": None, "veiculo": v.id, "modelo": v.modelo, "rank_carro": v.rank,
                       "t": t, "soc_chegada": soc, "origem": origem,
                       "kwh": max(0.0, ALVO - soc) / 100 * m.bateria_kwh})
    rank_por_id = {v.id: v.rank for v in cen.veiculos}
    modelo_por_id = {v.id: v.modelo for v in cen.veiculos}
    for r in res.retiradas:
        c = contratos[r.contrato_id]
        if c.devolucao_t is None:
            continue
        m = cen.modelos[modelo_por_id[r.veiculo_id]]
        soc = min(r.soc, (c.km_devolucao or 0.0) / m.autonomia_km * 100)
        linhas.append({"contrato": c.id, "veiculo": r.veiculo_id, "modelo": m.modelo,
                       "rank_carro": rank_por_id[r.veiculo_id], "t": max(c.devolucao_t, r.t),
                       "soc_chegada": soc, "origem": "devolucao",
                       "kwh": max(0.0, ALVO - soc) / 100 * m.bateria_kwh})
    return pd.DataFrame(linhas)


def contratos_rotulados(cen, res=None) -> pd.DataFrame:
    """tabela_contratos + o kWh real da devolução (só contratos atendidos e com devolução)."""
    res = res or simular(cen)
    s = sessoes_energia(cen, res)
    s = s[s.origem == "devolucao"][["contrato", "modelo", "rank_carro", "soc_chegada", "kwh"]]
    df = tabela_contratos(cen).merge(s, left_on="id", right_on="contrato", how="inner")
    df["upgrade"] = (df.rank_carro > df["rank"]).astype(int)
    return df.drop(columns=["contrato"])


# ---------------------------------------------------------------- dias

def tabela_dias(cen) -> pd.DataFrame:
    """Um dia (da janela pública) por linha: contagens e energia esperada que chega por hora."""
    ct = tabela_contratos(cen)
    ini, fim = tempo.JANELA_PUBLICA
    d0, d1 = ini // DIA, fim // DIA
    linhas = []
    for d in range(int(d0), int(d1)):
        a, b = d * DIA, (d + 1) * DIA
        ret = ct[(ct.retirada_t >= a) & (ct.retirada_t < b)]
        dev = ct[(ct.devolucao_t >= a) & (ct.devolucao_t < b)]
        j = cen.agencia.horario[tempo.dia_semana(a)]
        r = {"dia": d, "data": tempo.texto(a)[:9], "dia_sem": tempo.dia_semana(a),
             "horas_abertas": 0 if j is None else (j[1] - j[0]) / 60,
             "retiradas": len(ret), "devolucoes": len(dev), "kwh_esperado": float(dev.kwh_esperado.sum())}
        for rk in sorted(set(cen.categorias.values())):
            r[f"ret_rank{rk}"] = int((ret["rank"] == rk).sum())
        hr = ((ret.retirada_t - a) // 60).astype(int).value_counts()
        hd = dev.groupby(((dev.devolucao_t - a) // 60).astype(int)).kwh_esperado.sum()
        for h in range(24):
            r[f"ret_h{h:02d}"] = int(hr.get(h, 0))
            r[f"kwh_h{h:02d}"] = float(hd.get(h, 0.0))
        linhas.append(r)
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- agência

def folga_por_rank(cen) -> dict:
    """{rank: frota − máximo de carros fora ao mesmo tempo (contratos da categoria + frota em T0)}."""
    ev = []
    for v in cen.veiculos:
        if v.situacao == "em_contrato":
            ev += [(tempo.T0, 1, v.rank), (v.devolucao_t, -1, v.rank)]
    for c in cen.contratos:
        if c.devolucao_t is not None:
            ev += [(c.retirada_t, 1, c.rank), (c.devolucao_t, -1, c.rank)]
    ev.sort(key=lambda e: (e[0], e[1]))
    cur, mx = {}, {}
    for t, d, r in ev:
        cur[r] = cur.get(r, 0) + d
        if t < tempo.JANELA_PUBLICA[1]:
            mx[r] = max(mx.get(r, 0), cur[r])
    frota = pd.Series([v.rank for v in cen.veiculos]).value_counts()
    return {int(r): int(frota.get(r, 0)) - mx.get(r, 0) for r in sorted(set(cen.categorias.values()))}


def ficha_agencia(cen) -> dict:
    ag = cen.agencia
    ct = tabela_contratos(cen)
    ini, fim = tempo.JANELA_PUBLICA
    dias = (fim - ini) / DIA
    dev_jan = ct[(ct.devolucao_t >= ini) & (ct.devolucao_t < fim)]
    uteis = [ag.horario[d] for d in range(5)]
    fecha_uteis = [j[1] for j in uteis if j is not None]
    abre_na_ponta = any(j is not None and j[0] < tempo.PONTA[1] and j[1] > tempo.PONTA[0] for j in uteis)
    limite = cen.entradas[ag.entrada_existente].kw_util
    kwh_dia = float(dev_jan.kwh_esperado.sum() / dias)
    h_sem = horas_abertas_semana(cen)
    return {
        "agencia": ag.nome, "vagas": ag.vagas, "frota": len(cen.veiculos),
        "entrada_existente": ag.entrada_existente, "limite_kw": limite,
        "horas_abertas_semana": h_sem, "aberta_24h": h_sem >= 7 * 24 - 1e-9,
        "aberta_na_ponta": abre_na_ponta,
        "fecha_ate_18h": bool(fecha_uteis) and max(fecha_uteis) <= tempo.PONTA[0],
        "contratos": len(ct), "contratos_semana": len(ct) / 4,
        "kwh_dia": kwh_dia,
        "kwh_dia_por_vaga": kwh_dia / ag.vagas,
        "pressao_energia": kwh_dia / (limite * h_sem / 7) if h_sem else math.inf,  # >1: limite falta
        "devolucoes_dia": len(dev_jan) / dias,
        "devolucoes_dia_por_vaga": len(dev_jan) / dias / ag.vagas,
        "pct_devolve_na_abertura": float(ct.devolve_na_abertura.mean()),
        "folga_por_rank": folga_por_rank(cen),
        "em_contrato_t0_pct": float(np.mean([v.situacao == "em_contrato" for v in cen.veiculos])),
    }
