"""Medição em janelas de 15 min, métricas e séries (mesmo formato do juiz)."""
from dataclasses import dataclass

from .tempo import DIA, PONTA

PASSO = 15


@dataclass(slots=True)
class Retirada:
    t: float
    contrato_id: str
    veiculo_id: str
    rank_pedido: int
    rank_entregue: int
    soc: float


class Medidor:
    """Energia (kWh) por janela de 15 min. `bins[i]` = janela [15i, 15i+15)."""

    def __init__(self):
        self.bins: dict = {}

    def adicionar(self, a: float, b: float, kwh: float) -> None:
        """Espalha `kwh` uniformemente em [a, b] pelas janelas de 15 min."""
        if kwh <= 0 or b <= a:
            return
        taxa = kwh / (b - a)
        i = int(a // PASSO)
        while i * PASSO < b:
            sobra = min(b, (i + 1) * PASSO) - max(a, i * PASSO)
            if sobra > 0:
                self.bins[i] = self.bins.get(i, 0.0) + taxa * sobra
            i += 1


def _ponta(t: float) -> bool:
    dia, m = divmod(int(t), DIA)
    return (6 + dia) % 7 < 5 and PONTA[0] <= m < PONTA[1]


def metricas(retiradas, nao_atendidos, bins, ini, fim) -> dict:
    ats = [r for r in retiradas if ini <= r.t < fim]
    nao = sum(1 for t in nao_atendidos if ini <= t < fim)
    jan = [(PASSO * i, e) for i, e in bins.items() if ini <= PASSO * i < fim]
    contratos = len(ats) + nao
    return {
        "contratos": contratos,
        "certos": sum(1 for a in ats if a.rank_entregue == a.rank_pedido),
        "upgrades": sum(1 for a in ats if a.rank_entregue > a.rank_pedido),
        "nao_atendidos": nao,
        "pico_kw": max((e for _, e in jan), default=0.0) * 4.0,
        "energia_kwh": sum(e for _, e in jan),
        "energia_ponta_kwh": sum(e for t, e in jan if _ponta(t)),
        "atendimento_pct": 100.0 * len(ats) / contratos if contratos else 100.0,
    }


def series(bins, trace, retiradas, nao_atendidos, ini, fim) -> dict:
    """`trace`: lista de (t, plugados, fila)."""
    nb = int((fim - ini) // PASSO)
    base = int(ini) // PASSO
    pts = sorted({t: (n, f) for t, n, f in trace}.items())
    plug, fila, i, n, f = [0] * nb, [0] * nb, 0, 0, 0
    for k in range(nb):
        a = ini + PASSO * k
        while i < len(pts) and pts[i][0] <= a:
            n, f = pts[i][1]
            i += 1
        plug[k], fila[k] = n, f
        while i < len(pts) and pts[i][0] < a + PASSO:
            n, f = pts[i][1]
            plug[k], fila[k] = max(plug[k], n), max(fila[k], f)
            i += 1
    return {
        "inicio_min": int(ini),
        "passo_min": PASSO,
        "potencia_kw": [float(bins.get(base + k, 0.0)) * 4.0 for k in range(nb)],
        "plugados_max": plug,
        "fila_max": fila,
        "nao_atendidos_min": [float(t - ini) for t in nao_atendidos if ini <= t < fim],
        "soc_retirada": [float(r.soc) for r in retiradas if ini <= r.t < fim],
    }
