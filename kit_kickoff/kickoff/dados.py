"""Carrega o kit de dados de uma agência (CSV + agencias.md) num Cenario.

  python -m kickoff.dados Bangkok [--dados DIR]
"""
import csv
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import tempo
from .modelo import Agencia, Carregador, Cenario, Contrato, Entrada, ModeloVeiculo, VeiculoT0

RAIZ_KIT = Path(__file__).resolve().parent.parent
ARQUIVOS = ("agencias.md", "contratos_publicos.csv", "frota_t0.csv", "veiculos.csv", "categorias.csv",
            "carregadores.csv", "entrada_eletrica.csv")
DIAS_PY = {"Seg": 0, "Ter": 1, "Qua": 2, "Qui": 3, "Sex": 4, "Sáb": 5, "Dom": 6}


def _ler(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _faltando(dados_dir: Path, ag: str) -> None:
    pasta = dados_dir / ag
    esperado = [pasta / a for a in ARQUIVOS] + [pasta / "curvas"]
    if not pasta.is_dir() or any(not p.exists() for p in esperado):
        raise SystemExit(
            f"Dados de {ag} não encontrados em: {pasta}\n"
            f"Esperado: {', '.join(ARQUIVOS)} e curvas/*.md nessa pasta.\n"
            f"Baixe o kit da agência (python -m kickoff.api kit {ag}, ou /docs) e descompacte dentro de dados/ "
            f"(veja dados/COLOQUE_OS_DADOS_AQUI.md)."
        )


def _janela(texto: str):
    s = texto.strip()
    if s == "24h":
        return (0, 1440)
    if s == "fechado":
        return None

    def mins(x):
        h, m = x.split(":")
        return int(h) * 60 + int(m)

    a, b = s.split("-")
    fim = mins(b)
    if fim == 23 * 60 + 59:
        fim = 1440
    return (mins(a), fim)


def _agencia_md(texto: str, nome: str):
    vagas = int(re.search(r"\| Vagas elétricas \| (\d+) \|", texto).group(1))
    m = re.search(r"\| Frota \| (\d+) \|", texto)
    frota = int(m.group(1)) if m else 0
    existente = re.search(r"\| Entrada existente \| (.+?) \(", texto).group(1)
    horario = [None] * 7
    for m in re.finditer(r"^\| (Dom|Seg|Ter|Qua|Qui|Sex|Sáb) \| (.+?) \|$", texto, re.M):
        horario[DIAS_PY[m.group(1)]] = _janela(m.group(2))
    return Agencia(nome, vagas, frota, horario, ""), existente


def _linhas_md(texto: str) -> list:
    linhas = []
    for ln in texto.splitlines():
        ln = ln.strip()
        if not ln.startswith("|"):
            continue
        c = [x.strip() for x in ln.strip("|").split("|")]
        if c[0].startswith("-") or set(c[0]) <= {"-", ":"}:
            continue
        linhas.append(c)
    return linhas


def _curvas(pasta: Path) -> dict:
    """{modelo: (curva_ac, curva_dc)}: degrau i = média das linhas i e i+1 da tabela."""
    saida = {}
    for p in sorted(pasta.glob("*.md")):
        if p.name == "README.md":
            continue
        texto = p.read_text(encoding="utf-8")
        nome = texto.splitlines()[0].lstrip("# ").split(" — ")[0].strip()
        linhas = [c for c in _linhas_md(texto) if len(c) == 6 and c[0].endswith("%")]
        if len(linhas) != 21:
            raise SystemExit(f"curva {p.name}: {len(linhas)} pontos (esperado 21)")
        ac = [float(c[2]) for c in linhas]
        dc = [float(c[4]) for c in linhas]
        saida[nome] = ([(ac[i] + ac[i + 1]) / 2 for i in range(20)], [(dc[i] + dc[i + 1]) / 2 for i in range(20)])
    return saida


def carregar(dados_dir, agencia: str, catalogo=None) -> Cenario:
    """Cenário da agência na janela pública. `catalogo` (GET /catalogo pós-H4) preenche `custo`."""
    dados_dir = Path(dados_dir)
    _faltando(dados_dir, agencia)
    d = dados_dir / agencia

    ag, existente_desc = _agencia_md((d / "agencias.md").read_text(encoding="utf-8"), agencia)

    ent_rows = _ler(d / "entrada_eletrica.csv")
    custo_ent = {e["id"]: e["custo"] for e in (catalogo or {}).get("entradas", ()) if "custo" in e}
    entradas = {
        r["nivel_id"]: Entrada(r["nivel_id"], r["descricao"], float(r["kva"]), float(r["kw_util"]),
                               custo_ent.get(r["nivel_id"]))
        for r in ent_rows
    }
    por_desc = {r["descricao"]: r["nivel_id"] for r in ent_rows}
    if existente_desc not in por_desc:
        raise SystemExit(f"agencias.md: entrada existente '{existente_desc}' não está em {d / 'entrada_eletrica.csv'}")
    ag.entrada_existente = por_desc[existente_desc]

    custo_car = {c["id"]: c["custo"] for c in (catalogo or {}).get("carregadores", ()) if "custo" in c}
    carregadores = {
        r["modelo_id"]: Carregador(r["modelo_id"], r["modelo"], r["tipo"], float(r["potencia_kw"]),
                                   int(r["saidas"]), custo_car.get(r["modelo_id"]))
        for r in _ler(d / "carregadores.csv")
    }

    categorias = {r["grupo"]: int(r["rank"]) for r in _ler(d / "categorias.csv")}
    curvas = _curvas(d / "curvas")
    modelos = {}
    for r in _ler(d / "veiculos.csv"):
        if r["modelo"] not in curvas:
            raise SystemExit(f"modelos sem curva de carga: {r['modelo']}")
        ac, dc = curvas[r["modelo"]]
        modelos[r["modelo"]] = ModeloVeiculo(
            r["modelo"], r["grupo"], categorias[r["grupo"]], float(r["bateria_kwh"]), float(r["autonomia_km"]),
            float(r["recarga_ac_kw"]), float(r["recarga_dc_kw"]), ac, dc)

    veiculos = []
    for r in _ler(d / "frota_t0.csv"):
        m = modelos[r["modelo"]]
        fora = r["situacao"] == "em_contrato"
        dev = tempo.minutos(datetime.fromisoformat(r["devolucao_prevista"])) if fora else None
        soc_dev = float(r["soc_devolucao_pct"]) if fora else None
        veiculos.append(VeiculoT0(r["id"], m.modelo, m.categoria, m.rank, r["situacao"],
                                  soc_dev if fora else float(r["soc_pct"]), dev, soc_dev))

    contratos = []
    for r in _ler(d / "contratos_publicos.csv"):
        cat = r["categoria"]
        if cat not in categorias:
            continue
        ret = tempo.minutos(datetime.fromisoformat(r["retirada"]))
        dev = tempo.minutos(datetime.fromisoformat(r["devolucao"])) if r["devolucao"] else None
        if dev is not None and dev < ret:
            continue
        contratos.append(Contrato(r["id"], cat, categorias[cat], ret, dev, float(r["autonomia_min_retirada_km"]),
                                  float(r["km_devolucao"]) if r["km_devolucao"] else None))
    contratos.sort(key=lambda c: (c.retirada_t, c.id))

    return Cenario(ag, modelos, veiculos, contratos, carregadores, entradas, categorias)


def resumo(c: Cenario) -> str:
    ag = c.agencia
    ent = c.entradas[ag.entrada_existente]
    nomes = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")
    hor = ", ".join(
        f"{n} " + ("fechado" if j is None else f"{j[0] // 60:02d}:{j[0] % 60:02d}-{j[1] // 60:02d}:{j[1] % 60:02d}")
        for n, j in zip(nomes, ag.horario))
    linhas = [
        f"Agência {ag.nome}: {ag.vagas} vagas, frota {len(c.veiculos)}",
        f"Horário: {hor}",
        f"Entrada existente: {ent.id} ({ent.kva:g} kVA, {ent.kw_util:g} kW úteis)",
        "Frota por situação: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(v.situacao for v in c.veiculos).items())),
        "Frota por categoria: " + ", ".join(
            f"{k}={v}" for k, v in sorted(Counter(v.categoria for v in c.veiculos).items(), key=lambda kv: c.categorias[kv[0]])),
        f"Contratos: {len(c.contratos)} (" + ", ".join(
            f"{k}={v}" for k, v in sorted(Counter(x.categoria for x in c.contratos).items(), key=lambda kv: c.categorias[kv[0]])) + ")",
    ]
    if c.contratos:
        linhas.append(f"Primeira retirada: {tempo.texto(c.contratos[0].retirada_t)}; "
                      f"última: {tempo.texto(c.contratos[-1].retirada_t)}")
    return "\n".join(linhas)


def main(argv=None) -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m kickoff.dados")
    ap.add_argument("agencia")
    ap.add_argument("--dados", type=Path, default=RAIZ_KIT / "dados")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    print(resumo(carregar(a.dados, a.agencia)))


if __name__ == "__main__":
    main()
