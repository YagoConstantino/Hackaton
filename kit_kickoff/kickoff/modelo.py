"""Tipos de dados do cenário de uma agência."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Agencia:
    nome: str
    vagas: int
    frota: int
    horario: list  # 7 itens (seg=0..dom=6): None (fechado) ou (ini_min, fim_min) no dia
    entrada_existente: str


@dataclass(slots=True)
class ModeloVeiculo:
    modelo: str
    categoria: str
    rank: int
    bateria_kwh: float
    autonomia_km: float
    ac_max_kw: float
    dc_max_kw: float
    curva_ac: list  # 20 degraus de 5% de SOC, kW
    curva_dc: list


@dataclass(slots=True)
class VeiculoT0:
    id: str
    modelo: str
    categoria: str
    rank: int
    situacao: str  # estoque_pronto | estoque_a_carregar | em_contrato
    soc: float  # estoque: soc_pct; em_contrato: soc na devolução
    devolucao_t: Optional[int] = None
    soc_devolucao: Optional[float] = None


@dataclass(slots=True)
class Contrato:
    id: str
    categoria: str
    rank: int
    retirada_t: int
    devolucao_t: Optional[int]
    autonomia_min_retirada_km: float
    km_devolucao: Optional[float]


@dataclass(slots=True)
class Carregador:
    id: str
    modelo: str
    tipo: str  # AC | DC
    potencia_kw: float
    saidas: int
    custo: Optional[float] = None


@dataclass(slots=True)
class Entrada:
    id: str
    descricao: str
    kva: float
    kw_util: float
    custo: Optional[float] = None


@dataclass(slots=True)
class Cenario:
    agencia: Agencia
    modelos: dict = field(default_factory=dict)
    veiculos: list = field(default_factory=list)
    contratos: list = field(default_factory=list)
    carregadores: dict = field(default_factory=dict)
    entradas: dict = field(default_factory=dict)
    categorias: dict = field(default_factory=dict)
