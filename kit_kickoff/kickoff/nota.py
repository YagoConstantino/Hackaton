"""Custo de obra e pontuação (regulamento 8). Pesos e custos só saem em H4."""

ITENS = (
    ("certo", "certos"),
    ("upgrade", "upgrades"),
    ("nao_atendido", "nao_atendidos"),
    ("demanda_contratada", "demanda_contratada_kw"),
    ("energia_ponta_kwh", "energia_ponta_kwh"),
    ("infraestrutura", "custo_infra"),
)


def custo_infra(sub_normalizada: dict, cenario):
    """{'carregadores', 'entrada', 'total'} ou None se faltar algum custo (catálogo pré-H4)."""
    car = 0
    for k, n in sub_normalizada["carregadores"].items():
        c = cenario.carregadores[k].custo
        if c is None:
            return None
        car += n * c
    e = sub_normalizada["entrada"]
    if e == cenario.agencia.entrada_existente:
        ent = 0
    else:
        ent = cenario.entradas[e].custo
        if ent is None:
            return None
    return {"carregadores": car, "entrada": ent, "total": car + ent}


def pontuar(metricas: dict, pesos: dict) -> dict:
    itens = [[r, metricas[k], pesos[r], metricas[k] * pesos[r]] for r, k in ITENS]
    return {"itens": itens, "nota": sum(i[3] for i in itens)}
