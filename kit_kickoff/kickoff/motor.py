"""Esqueleto do simulador de eventos discretos.

O laço de eventos, o estado e a medição estão prontos. As regras de operação são os métodos
marcados com `# TODO(etapa N)`: sem implementá-los, todo cliente é perdido (atendimento 0%).

Ordem no mesmo minuto (regulamento 5.1): devolução -> abertura/ponta/eventos -> fim de recarga
-> retirada -> fechamento (constantes PRIO_*).
"""
import heapq
from dataclasses import dataclass, field
from typing import Optional

from . import potencia, tempo, validar
from .medicao import Medidor, Retirada
from .modelo import Cenario, Carregador, ModeloVeiculo

PRIO_DEVOLUCAO = 0
PRIO_ABERTURA = 1  # abertura, início/fim da ponta e eventos
PRIO_FIM_RECARGA = 2
PRIO_RETIRADA = 3
PRIO_FECHAMENTO = 4


@dataclass(eq=False)
class Veiculo:
    id: str
    modelo: ModeloVeiculo
    rank: int
    soc: float
    alvo: float = validar.SOC_ALVO
    plugado: bool = False
    na_fila: bool = False
    entrou_fila_t: Optional[float] = None
    carregador: Optional["Ponto"] = None
    potencia_kw: float = 0.0
    token: int = 0  # incrementar para invalidar 'fim_recarga' já agendado
    soc_limite: Optional[float] = None  # teto do degrau atual; `avancar` nunca passa dele


@dataclass(eq=False)
class Ponto:
    """Instância de carregador (ex.: 'ac_7-0')."""
    id: str
    modelo: Carregador
    conectados: list = field(default_factory=list)
    quebrado: bool = False

    @property
    def livres(self) -> int:
        return self.modelo.saidas - len(self.conectados)


@dataclass
class Resultado:
    retiradas: list
    nao_atendidos: list
    bins: dict
    trace: list
    violacoes: list


class Motor:
    def __init__(self, cenario: Cenario, sub: dict, eventos=()):
        """`sub` é a submissão normalizada (validar.normalizar)."""
        self.cen = cenario
        self.sub = sub
        self.pol = sub["politica"]
        self.limite_kw = validar.limite_kw(sub, cenario)
        self.t = tempo.T0
        self.heap: list = []
        self.seq = 0
        self.medidor = Medidor()
        self.retiradas: list = []
        self.nao_atendidos: list = []
        self.trace: list = []
        self.violacoes: list = []
        self.patio: dict = {}
        self.fila: list = []
        self.aberta = tempo.aberta(cenario.agencia, tempo.T0)
        self.em_ponta = self.pol["evitar_ponta"] and tempo.eh_ponta(tempo.T0)
        self.contratos = {c.id: c for c in cenario.contratos}
        self.veiculos = {
            v.id: Veiculo(v.id, cenario.modelos[v.modelo], v.rank, v.soc) for v in cenario.veiculos
        }
        self.pontos = []
        for modelo_id in sorted(sub["carregadores"]):  # 6.3.4: empate pelo id em ordem alfabética
            for i in range(sub["carregadores"][modelo_id]):
                self.pontos.append(Ponto(f"{modelo_id}-{i}", cenario.carregadores[modelo_id]))
        self.eventos = eventos

    # ---------- pronto: laço de eventos ----------

    def agendar(self, t: float, prio: int, tipo: str, *payload) -> None:
        self.seq += 1
        heapq.heappush(self.heap, (t, prio, self.seq, tipo, payload))

    def _agendar_inicio(self) -> None:
        cen, ag = self.cen, self.cen.agencia
        fim_dados = max((c.devolucao_t if c.devolucao_t is not None else c.retirada_t) for c in cen.contratos) \
            if cen.contratos else tempo.T0
        horizonte = fim_dados + 4 * tempo.DIA
        d0, d1 = tempo.T0 // tempo.DIA, horizonte // tempo.DIA

        # abertura/fechamento: junta dias seguidos (ex.: 24h) e só marca as bordas
        blocos = []
        for d in range(d0 - 1, d1 + 2):
            j = ag.horario[(6 + d) % 7]
            if j is None:
                continue
            ini, fim = d * tempo.DIA + j[0], d * tempo.DIA + j[1]
            if blocos and blocos[-1][1] == ini:
                blocos[-1][1] = fim
            else:
                blocos.append([ini, fim])
        for ini, fim in blocos:
            if ini >= tempo.T0:
                self.agendar(ini, PRIO_ABERTURA, "abertura")
            if tempo.T0 < fim <= horizonte + tempo.DIA:
                self.agendar(fim, PRIO_FECHAMENTO, "fechamento")

        if self.pol["evitar_ponta"]:
            for d in range(d0, d1 + 1):
                if (6 + d) % 7 < 5:
                    ini, fim = d * tempo.DIA + tempo.PONTA[0], d * tempo.DIA + tempo.PONTA[1]
                    if ini > tempo.T0:
                        self.agendar(ini, PRIO_ABERTURA, "ponta", True)
                    if fim > tempo.T0:
                        self.agendar(fim, PRIO_ABERTURA, "ponta", False)

        for vt in sorted(cen.veiculos, key=lambda x: x.id):
            if vt.situacao == "em_contrato":
                self.agendar(max(vt.devolucao_t, tempo.T0), PRIO_DEVOLUCAO, "devolucao", vt.id, vt.soc_devolucao)
            else:
                self.entrar_patio(self.veiculos[vt.id], tempo.T0)
        for c in cen.contratos:
            self.agendar(c.retirada_t, PRIO_RETIRADA, "retirada", c.id)
        self.agendar_eventos(self.eventos)
        self.anotar(tempo.T0)

    def rodar(self) -> Resultado:
        self._agendar_inicio()
        while self.heap:
            t, _, _, tipo, p = heapq.heappop(self.heap)
            self.avancar(t)
            if tipo == "devolucao":
                self.on_devolucao(p[0], p[1], t)
            elif tipo == "abertura":
                self.on_abertura(t)
            elif tipo == "fechamento":
                self.on_fechamento(t)
            elif tipo == "ponta":
                self.on_ponta(p[0], t)
            elif tipo == "evento":
                self.on_evento(t, *p)
            elif tipo == "fim_recarga":
                self.on_fim_recarga(p[0], p[1], t)
            elif tipo == "retirada":
                self.on_retirada(p[0], t)
            self.anotar(t)
        return Resultado(self.retiradas, self.nao_atendidos, self.medidor.bins, self.trace, self.violacoes)

    def avancar(self, t: float) -> None:
        """Integra a recarga de self.t até t com as potências vigentes e mede a energia."""
        dt = t - self.t
        if dt > 0:
            for ponto in self.pontos:
                for v in ponto.conectados:
                    if v.potencia_kw > 0 and v.soc < v.alvo:
                        teto = min(v.alvo, v.soc_limite) if v.soc_limite is not None else v.alvo
                        novo = min(teto, v.soc + v.potencia_kw * dt / 60.0 / v.modelo.bateria_kwh * 100.0)
                        self.medidor.adicionar(self.t, t, (novo - v.soc) / 100.0 * v.modelo.bateria_kwh)
                        v.soc = novo
            self.t = t

    def anotar(self, t: float) -> None:
        """Registra (t, plugados, fila) quando muda."""
        ponto = (sum(1 for v in self.patio.values() if v.plugado), len(self.fila))
        if not self.trace or self.trace[-1][1:] != ponto:
            self.trace.append((t, *ponto))

    # ---------- pronto: auxiliares de estado ----------

    def plugar(self, v: Veiculo, ponto: Ponto) -> None:
        """Só contabilidade: conecta v em ponto e tira da fila. Não decide nem calcula potência."""
        if v.na_fila:
            self.fila.remove(v)
            v.na_fila = False
        ponto.conectados.append(v)
        v.plugado, v.carregador = True, ponto

    def desplugar(self, v: Veiculo) -> None:
        if v.carregador is not None:
            v.carregador.conectados.remove(v)
        v.plugado, v.carregador, v.potencia_kw, v.soc_limite = False, None, 0.0, None
        v.token += 1

    def sair_do_patio(self, v: Veiculo) -> None:
        if v.plugado:
            self.desplugar(v)
        if v.na_fila:
            self.fila.remove(v)
            v.na_fila = False
        v.token += 1
        self.patio.pop(v.id, None)

    def violar(self, msg: str) -> None:
        self.violacoes.append(f"{tempo.texto(self.t)}: {msg}")

    def checar_ocupacao(self) -> None:
        """plugados <= saídas instaladas <= vagas (5.2)."""
        saidas = sum(p.modelo.saidas for p in self.pontos)
        plugados = sum(len(p.conectados) for p in self.pontos)
        if plugados > saidas:
            self.violar(f"{plugados} plugados > {saidas} saídas")
        if saidas > self.cen.agencia.vagas:
            self.violar(f"{saidas} saídas > {self.cen.agencia.vagas} vagas")

    # ---------- pronto: retirada ----------

    def on_retirada(self, contrato_id: str, t: float) -> None:
        self.avancar(t)
        c = self.contratos[contrato_id]
        self._init_reservas()
        self._feitos.add(c.id)
        v = self.escolher_carro(c, t)
        if v is None:
            self.nao_atendidos.append(t)
            return
        estava_plugado = v.plugado
        self.sair_do_patio(v)
        self.retiradas.append(Retirada(t, c.id, v.id, c.rank, v.rank, v.soc))
        if c.devolucao_t is not None:
            self.agendar(max(c.devolucao_t, t), PRIO_DEVOLUCAO, "devolucao", v.id, self.soc_devolucao(v, c))
        if estava_plugado:
            self.recalcular_potencias(t)

    # ================= regras de operação (implementadas) =================

    EPS = 1e-9

    def soc_devolucao(self, v: Veiculo, c) -> float:
        """4.1: SOC = km_devolucao / autonomia_km * 100, nunca acima do SOC de saída."""
        if c.km_devolucao is None:
            return v.soc
        return min(v.soc, c.km_devolucao / v.modelo.autonomia_km * 100.0)

    def entrar_patio(self, v: Veiculo, t: float) -> None:
        """5.2: abaixo de 80% vai para a fila; depois tenta plugar e recalcula."""
        self.patio[v.id] = v
        if v.soc < v.alvo - self.EPS:
            v.na_fila = True
            v.entrou_fila_t = t
            self.fila.append(v)
            self.plugar_fila(t)
            self.recalcular_potencias(t)

    def escolher_carro(self, c, t: float) -> Optional[Veiculo]:
        """5.1/6.3.1: categoria >= pedida e SOC >= 80; menor upgrade -> menor SOC -> não plugado -> id."""
        if not self.aberta:
            return None
        aptos = [v for v in self.patio.values() if v.rank >= c.rank and v.soc >= validar.SOC_ALVO - 1e-7]
        if not aptos:
            return None
        return min(aptos, key=lambda v: (v.rank - c.rank, v.soc, v.plugado, v.id))

    # --- próxima reserva compatível (6.3.3) ---
    def _init_reservas(self) -> None:
        if not hasattr(self, "_cts"):
            self._cts = sorted(self.cen.contratos, key=lambda c: (c.retirada_t, c.id))
            self._ptr = 0
            self._feitos = set()
            self._ranks = sorted({m.rank for m in self.cen.modelos.values()})

    def _prox_reserva(self) -> dict:
        """rank do carro -> instante da 1ª reserva ainda não retirada com categoria <= rank."""
        self._init_reservas()
        while self._ptr < len(self._cts) and self._cts[self._ptr].id in self._feitos:
            self._ptr += 1
        out, menor = {}, None
        for c in self._cts[self._ptr:]:
            if c.id in self._feitos:
                continue
            if menor is None or c.rank < menor:
                menor = c.rank
                for r in self._ranks:
                    if r >= c.rank and r not in out:
                        out[r] = c.retirada_t
                if menor == self._ranks[0]:
                    break
        return out

    def chave_prioridade(self):
        """Função de ordenação da política (usada na fila e na divisão `prioridade`)."""
        pr = self.pol["prioridade"]
        if pr == "chegada":
            return lambda v: (v.entrou_fila_t if v.entrou_fila_t is not None else 0.0, v.id)
        if pr == "menor_soc":
            return lambda v: (v.modelo.autonomia_km * v.soc / 100.0, v.id)
        res = self._prox_reserva()
        inf = float("inf")
        return lambda v: (res.get(v.rank, inf), -v.soc, v.id)

    def ordenar_fila(self, t: float) -> None:
        self.fila.sort(key=self.chave_prioridade())

    def _divide(self, total: float, caps: list) -> list:
        if self.pol["divisao"] == "prioridade":
            return potencia.sequencial(total, caps)
        return potencia.enchimento_agua(total, caps)

    def escolher_ponto(self, v: Veiculo) -> Optional[Ponto]:
        """6.3.4: ponto em operação com saída livre que daria mais potência a v (divisão igual estimada)."""
        melhor, melhor_kw = None, -1.0
        for p in self.pontos:
            if p.quebrado or p.livres <= 0:
                continue
            tipo = p.modelo.tipo
            outros = [u for u in p.conectados if u.soc < u.alvo - self.EPS]
            caps = [potencia.potencia_curva(u.modelo, u.soc, tipo) for u in outros]
            caps.append(potencia.potencia_curva(v.modelo, v.soc, tipo))
            kw = potencia.enchimento_agua(p.modelo.potencia_kw, caps)[-1]
            if kw > melhor_kw + 1e-9:
                melhor, melhor_kw = p, kw
        return melhor

    def plugar_fila(self, t: float) -> None:
        """5.2: só aberta, na ordem da fila, enquanto houver saída livre em operação."""
        if not self.aberta or not self.fila:
            return
        self.ordenar_fila(t)
        for v in list(self.fila):
            p = self.escolher_ponto(v)
            if p is None:
                break
            self.plugar(v, p)
        self.checar_ocupacao()

    def recalcular_potencias(self, t: float) -> None:
        """5.3/6.3.5: camada 1 (carregador) e camada 2 (limite da agência), conforme `divisao`."""
        chave = self.chave_prioridade() if self.pol["divisao"] == "prioridade" else None
        carregando, cap1 = [], {}
        for p in self.pontos:
            ativos = [u for u in p.conectados if u.soc < u.alvo - self.EPS]
            for u in p.conectados:
                u.potencia_kw = 0.0
            if p.quebrado or self.em_ponta or not ativos:
                continue
            if chave:
                ativos.sort(key=chave)
            caps = [potencia.potencia_curva(u.modelo, u.soc, p.modelo.tipo) for u in ativos]
            for u, kw in zip(ativos, self._divide(p.modelo.potencia_kw, caps)):
                cap1[u.id] = kw
                carregando.append(u)
        if carregando:
            if sum(cap1[u.id] for u in carregando) > self.limite_kw + 1e-9:
                if chave:
                    carregando.sort(key=chave)
                kws = self._divide(self.limite_kw, [cap1[u.id] for u in carregando])
            else:
                kws = [cap1[u.id] for u in carregando]
            for u, kw in zip(carregando, kws):
                u.potencia_kw = kw
        for p in self.pontos:
            for u in p.conectados:
                self.agendar_fim_degrau(u, t)

    def agendar_fim_degrau(self, v: Veiculo, t: float) -> None:
        """6.3.2: agenda 'fim_recarga' no próximo degrau de 5% ou no alvo."""
        v.token += 1
        if v.soc >= v.alvo - self.EPS:
            v.soc_limite = None
            return
        i = int(v.soc / 5 + 1e-9)
        lim = min(v.alvo, (i + 1) * 5.0)
        v.soc_limite = lim
        if v.potencia_kw <= 1e-12:
            return
        dt = (lim - v.soc) / 100.0 * v.modelo.bateria_kwh / v.potencia_kw * 60.0
        self.agendar(t + dt, PRIO_FIM_RECARGA, "fim_recarga", v.id, v.token)

    def on_fim_recarga(self, vid: str, token: int, t: float) -> None:
        v = self.veiculos[vid]
        if token != v.token or not v.plugado:
            return
        if v.soc_limite is not None and abs(v.soc - v.soc_limite) < 1e-6:
            v.soc = v.soc_limite
        if v.soc >= v.alvo - self.EPS:
            v.soc = max(v.soc, v.alvo)
            if self.aberta:
                self.desplugar(v)
            self.plugar_fila(t)
        self.recalcular_potencias(t)

    def on_devolucao(self, vid: str, soc: float, t: float) -> None:
        v = self.veiculos[vid]
        v.soc = soc
        self.entrar_patio(v, t)

    def on_abertura(self, t: float) -> None:
        self.aberta = True
        for p in self.pontos:
            for u in list(p.conectados):
                if u.soc >= u.alvo - self.EPS:
                    self.desplugar(u)
        self.plugar_fila(t)
        self.recalcular_potencias(t)

    def on_fechamento(self, t: float) -> None:
        self.aberta = False

    def on_ponta(self, inicio: bool, t: float) -> None:
        self.em_ponta = inicio
        self.recalcular_potencias(t)

    def agendar_eventos(self, eventos) -> None:
        """Agenda os eventos ao vivo (seção 11). `eventos`: lista de `params` (minutos desde 17/10/2049 00:00).

        O significado e o formato de `params` são explicados no anúncio de cada evento; vêm de
        `eventos_ativos` de GET /status. Ex. de uso: `self.agendar(t, PRIO_ABERTURA, 'evento', params)`.
        """
        # formato real ainda não anunciado; para testes próprios usamos ("quebra", ponto_id, bool)
        for e in eventos:
            pass

    def on_evento(self, t: float, *params) -> None:
        """Aplica um evento no instante t (ex.: limite da concessionária, carregador fora de operação).

        Recalcule as potências; ao voltar um carregador, tente plugar a fila (6.3.3).
        Formato próprio de teste: ("quebra", ponto_id, True/False).
        """
        if params and params[0] == "quebra":
            _, pid, quebrado = params
            for p in self.pontos:
                if p.id == pid:
                    p.quebrado = quebrado
            if not quebrado:
                self.plugar_fila(t)
            self.recalcular_potencias(t)


def simular(cenario: Cenario, sub_normalizada: dict, eventos=()) -> Resultado:
    return Motor(cenario, sub_normalizada, eventos).rodar()
