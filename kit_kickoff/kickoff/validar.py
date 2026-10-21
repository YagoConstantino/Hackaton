"""Validação e normalização da submissão (regulamento 6.2). Mesmas mensagens do juiz."""
import math

CHAVES = {"agencia", "carregadores", "entrada", "demanda_contratada_kw", "politica"}
B3_KVA = 75  # até aqui é baixa tensão (B3), sem demanda contratada
DEMANDA_MIN_KW = 30
DEMANDA_MAX_KW = 2000
DEMANDA_PASSO_KW = 10
SOC_ALVO = 80.0
MENU = {
    "prioridade": ("menor_soc", "chegada", "proxima_retirada"),
    "evitar_ponta": (False, True),
    "divisao": ("igual", "prioridade"),
}
PADRAO = {"prioridade": "menor_soc", "evitar_ponta": False, "divisao": "igual"}


def _no_menu(k, v) -> bool:
    if k == "evitar_ponta":
        return isinstance(v, bool)
    return not isinstance(v, bool) and v in MENU[k]


def arredondar_demanda(d: float) -> int:
    """Múltiplo de 10 kW mais próximo; o 5 sobe (75 -> 80)."""
    return int(math.floor(d / DEMANDA_PASSO_KW + 0.5)) * DEMANDA_PASSO_KW


def teto_demanda(entrada) -> int:
    """kW útil da entrada arredondado para baixo ao múltiplo de 10, até 2000."""
    return min(DEMANDA_MAX_KW, int(entrada.kw_util // DEMANDA_PASSO_KW) * DEMANDA_PASSO_KW)


def validar(sub, cenario) -> list:
    if not isinstance(sub, dict):
        return ["submissão deve ser um objeto"]
    erros = [f"chave desconhecida: {k}" for k in sub if k not in CHAVES]
    nome = sub.get("agencia")
    ag = cenario.agencia if isinstance(nome, str) and nome == cenario.agencia.nome else None
    if ag is None:
        erros.append(f"agência desconhecida: {nome}")
    car = sub.get("carregadores") or {}
    if not isinstance(car, dict):
        erros.append("carregadores deve ser um objeto")
        car = {}
    total = saidas = 0
    for k, n in car.items():
        if k not in cenario.carregadores:
            erros.append(f"carregador desconhecido: {k}")
        elif isinstance(n, bool) or not isinstance(n, int) or n < 0:
            erros.append(f"quantidade inválida para {k}: {n!r}")
        else:
            total += n
            saidas += n * cenario.carregadores[k].saidas
    if total == 0:
        erros.append("nenhum carregador")
    if ag is not None and saidas > ag.vagas:
        erros.append(f"{saidas} saídas > {ag.vagas} vagas")
    e = sub.get("entrada")
    ent = cenario.entradas.get(e) if isinstance(e, str) else None
    ex = ag.entrada_existente if ag is not None else None
    if ent is None:
        erros.append(f"entrada desconhecida: {e}")
    elif e != ex:
        if ent.kva < B3_KVA:
            erros.append(f"entrada {e} disponível só como existente")
        if ex in cenario.entradas and ent.kw_util < cenario.entradas[ex].kw_util:
            erros.append(f"entrada {e} abaixo da existente {ex}")
    if "demanda_contratada_kw" in sub and ent is not None:
        d = sub["demanda_contratada_kw"]
        if ent.kva <= B3_KVA:
            erros.append(f"demanda contratada só existe com entrada acima de {B3_KVA} kVA (A4/SE)")
        elif d is not None:
            faixa = f"demanda_contratada_kw deve estar entre {DEMANDA_MIN_KW} e {teto_demanda(ent)} kW, em passos de {DEMANDA_PASSO_KW}"
            if isinstance(d, bool) or not isinstance(d, (int, float)) or not math.isfinite(d):
                erros.append(f"{faixa}: {d!r}")
            elif not DEMANDA_MIN_KW <= arredondar_demanda(d) <= teto_demanda(ent):
                erros.append(f"{faixa}: {d!r} (arredondado para {arredondar_demanda(d)})")
    if "politica" in sub and not isinstance(sub["politica"], dict):
        erros.append("politica deve ser um objeto")
        pol = {}
    else:
        pol = sub.get("politica") or {}
    for k, v in pol.items():
        if k not in MENU:
            erros.append(f"chave de política desconhecida: {k}")
        elif not _no_menu(k, v):
            erros.append(f"{k} fora do menu: {v!r}")
    return erros


def demanda_kw(sub: dict, cenario):
    """Demanda contratada efetiva: None em B3; em A4/SE o valor arredondado ou, se omitido, o teto."""
    ent = cenario.entradas[sub["entrada"]]
    if ent.kva <= B3_KVA:
        return None
    d = sub.get("demanda_contratada_kw")
    return teto_demanda(ent) if d is None else arredondar_demanda(d)


def normalizar(sub: dict, cenario) -> dict:
    """Forma canônica de uma submissão válida."""
    car = sub["carregadores"]
    return {
        "agencia": sub["agencia"],
        "carregadores": {k: car[k] for k in sorted(car) if car[k] > 0},
        "entrada": sub["entrada"],
        "demanda_contratada_kw": demanda_kw(sub, cenario),
        "politica": {**PADRAO, **(sub.get("politica") or {})},
    }


def limite_kw(sub_normalizada: dict, cenario) -> float:
    """Limite da agência: demanda contratada (A4/SE) ou kW útil da entrada (B3)."""
    dem = sub_normalizada["demanda_contratada_kw"]
    return cenario.entradas[sub_normalizada["entrada"]].kw_util if dem is None else dem
