"""Potência do carro pela curva e repartição de potência (regulamento 5.3 e 6.3.5)."""


def potencia_curva(modelo, soc: float, tipo: str) -> float:
    """kW que o carro absorve no degrau de SOC atual. tipo: 'AC' ou 'DC'. Índice min(19, floor(soc/5))."""
    curva = modelo.curva_ac if tipo == "AC" else modelo.curva_dc
    return curva[min(19, int(soc / 5 + 1e-9))]


def enchimento_agua(total: float, caps: list) -> list:
    """Divisão `igual` (6.3.5): partes iguais; quem não absorve a parte fica com o teto e a sobra
    é redistribuída entre os demais.

    Ex.: total 80, caps [30, 30, 26.6, 16.45] -> parte 20; o 4º só absorve 16.45;
    sobra 3.55 -> os outros três ficam com 21.18333.
    Ex.: total 40.5, mesmos caps -> 10.125 para cada um.
    """
    n = len(caps)
    atribuido = [0.0] * n
    ativos = list(range(n))
    resta = float(total)
    while ativos and resta > 1e-9:
        parte = resta / len(ativos)
        cheios = [i for i in ativos if caps[i] <= parte + 1e-9]
        if not cheios:
            for i in ativos:
                atribuido[i] = parte
            break
        for i in cheios:
            atribuido[i] = caps[i]
            resta -= caps[i]
            ativos.remove(i)
    return atribuido


def sequencial(total: float, caps: list) -> list:
    """Divisão `prioridade` (6.3.5): na ordem da lista, cada um leva min(teto, que sobrou).

    Ex.: total 40.5, caps (ordem Kwid, Geely, JAC, Dolphin) [26.6, 30, 16.45, 30]
    -> [26.6, 13.9, 0, 0].
    """
    resta = float(total)
    saida = []
    for c in caps:
        p = max(0.0, min(c, resta))
        saida.append(p)
        resta -= p
    return saida
