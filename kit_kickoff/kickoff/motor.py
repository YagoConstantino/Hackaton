"""Esqueleto do simulador de eventos discretos.

O laço de eventos, o estado e a medição estão prontos. As regras de operação são os métodos
marcados com `# TODO(etapa N)`: sem implementá-los, todo cliente é perdido (atendimento 0%).

Ordem no mesmo minuto (regulamento 5.1): devolução -> abertura/ponta/eventos -> fim de recarga
-> retirada -> fechamento (constantes PRIO_*).
"""
import bisect
import heapq
import math
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

EPS = 1e-9  # tolerância de ponto flutuante para SOC/potência

# Leitura da regra 6.3.4 (estimativa do carregador): "simples" = min(nominal/n, curva do carro);
# "agua" = enchimento de água com quem já está no carregador. Trocar se o juiz divergir.
ESTIMATIVA_PONTO = "simples"
CASAS_ORDEM = 6  # arredondamento de km/SOC nas ordenações da fila (empates exatos vão para o id)
# Carro num carregador que quebra: False = continua plugado a 0 kW (não troca de carregador, 5.4);
# True = volta para a fila. Confirmar no anúncio do evento.
EVENTO_QUEBRA_DESPLUGA = False

# Série `fila_max` como o juiz a reporta (inferido comparando com POST /teste completo em Bangkok).
# O juiz NÃO grava o tamanho da fila a cada mudança: grava o valor real na devolução, grava 0 quando
# um carro chega a 80% e é desplugado, e não grava nada em retirada/troca de degrau (mantém o anterior).
# "real" = grava len(fila); "zero" = grava 0; "skip" = não grava. Só afeta a série reportada;
# a fila verdadeira (usada na simulação) fica em `Motor.trace_real`.
# abertura/fechamento/perdido/t0: o teste 01 não distingue; confirmar com os testes 02–08.
REGISTRO_FILA = {
    "t0": "real",
    "devolucao": "real",
    "fim80": "zero",
    "abertura": "real",
    "fechamento": "skip",
}


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
        # contratos em ordem de retirada; os já processados (atendidos ou perdidos) formam um prefixo
        self._contratos_ord = list(cenario.contratos)
        self._processados: set = set()
        self._ptr = 0
        # por rank do carro: índices (em _contratos_ord) dos contratos com rank <= esse rank
        ranks = sorted(set(cenario.categorias.values()) | {v.rank for v in self.veiculos.values()})
        self._idx_por_rank = {
            r: [i for i, c in enumerate(self._contratos_ord) if c.rank <= r] for r in ranks
        }
        self.limite_base_kw = self.limite_kw
        self.fila_serie = 0  # valor da fila como o juiz reporta na série (REGISTRO_FILA)
        self.trace_real: list = []  # (t, plugados, fila verdadeira), para o dashboard

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
        """Registra (t, plugados, fila) quando muda. A fila do `trace` segue o critério do juiz
        (REGISTRO_FILA); a fila verdadeira vai para `trace_real`."""
        plugados = sum(1 for v in self.patio.values() if v.plugado)
        ponto = (plugados, self.fila_serie)
        if not self.trace or self.trace[-1][1:] != ponto:
            self.trace.append((t, *ponto))
        real = (plugados, len(self.fila))
        if not self.trace_real or self.trace_real[-1][1:] != real:
            self.trace_real.append((t, *real))

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

    # ---------- auxiliares da equipe ----------

    def _marcar_processado(self, c) -> None:
        """Contrato c chegou à hora da retirada (atendido ou perdido): deixa de ser reserva futura."""
        self._processados.add(c.id)
        while self._ptr < len(self._contratos_ord) and self._contratos_ord[self._ptr].id in self._processados:
            self._ptr += 1

    def _proxima_reserva(self, v: Veiculo) -> float:
        """Horário do primeiro contrato ainda não retirado com categoria <= a de v (inf se não houver)."""
        idx = self._idx_por_rank.get(v.rank, [])
        k = bisect.bisect_left(idx, self._ptr)
        while k < len(idx):
            c = self._contratos_ord[idx[k]]
            if c.id not in self._processados:
                return c.retirada_t
            k += 1
        return math.inf

    def _chave_prioridade(self, v: Veiculo):
        """Chave de ordenação da política (6.3.3); usada na fila e na divisão `prioridade` (6.3.5)."""
        # km e SOC arredondados (CASAS_ORDEM): km_devolucao é inteiro, então muitos carros empatam
        # exatamente; sem arredondar, o ruído de ponto flutuante de autonomia × (km/autonomia) decidia
        # o empate em vez do id. Confirmado contra o juiz (teste 08 de validacao/).
        pr = self.pol["prioridade"]
        if pr == "chegada":
            t = v.entrou_fila_t if v.entrou_fila_t is not None else math.inf
            return (t, v.id)
        if pr == "proxima_retirada":
            return (self._proxima_reserva(v), -round(v.soc, CASAS_ORDEM), v.id)
        return (round(v.modelo.autonomia_km * v.soc / 100.0, CASAS_ORDEM), v.id)  # menor_soc: km restantes

    def _registrar_fila(self, evento: str) -> None:
        """Atualiza o valor da fila reportado na série, conforme REGISTRO_FILA."""
        modo = REGISTRO_FILA.get(evento, "skip")
        if modo == "real":
            self.fila_serie = len(self.fila)
        elif modo == "zero":
            self.fila_serie = 0

    def _curva(self, v: Veiculo, ponto: "Ponto") -> float:
        return potencia.potencia_curva(v.modelo, v.soc, ponto.modelo.tipo)

    # ================= TODO: regras de operação =================

    def soc_devolucao(self, v: Veiculo, c) -> float:
        """SOC com que o carro volta (regulamento 4.1).

        SOC = km_devolucao / autonomia_km do modelo que atendeu * 100, nunca acima do SOC com que saiu
        (`v.soc` neste momento). `c.km_devolucao` é a autonomia restante em km.
        """
        if c.km_devolucao is None:
            return v.soc
        return min(v.soc, c.km_devolucao / v.modelo.autonomia_km * 100.0)

    def entrar_patio(self, v: Veiculo, t: float) -> None:
        """Carro entra no pátio (T0 ou devolução).

        Abaixo do SOC alvo (80%) vai para a fila de recarga (5.2), registrando `entrou_fila_t`;
        acima, fica apto no pátio. Depois tente plugar (`plugar_fila`) e recalcule as potências.
        """
        self.patio[v.id] = v
        if v.soc < v.alvo - EPS and not v.na_fila:
            v.na_fila = True
            v.entrou_fila_t = t
            self.fila.append(v)
        self.plugar_fila(t)
        self.recalcular_potencias(t)
        self._registrar_fila("t0" if t <= tempo.T0 else "devolucao")

    def escolher_carro(self, c, t: float) -> Optional[Veiculo]:
        """Carro do pátio para o contrato c, ou None (cliente perdido). Regulamento 5.1 e 6.3.1.

        Elegível: categoria >= pedida (`v.rank >= c.rank`; upgrade sim, downgrade nunca) e SOC >= 80%.
        Ordem: menor upgrade -> menor SOC -> não plugado -> menor `id` (alfabético).
        Ex. 6.3.1 (contrato Prata): Geely 82% sem upgrade e menor SOC entre os aptos sai antes do
        Dolphin Mini 95% plugado; com o Geely a 78%, sai o Dolphin Mini; sem Prata apto, sai o MG4 (upgrade).
        Com a agência fechada, ninguém retira (os contratos já vêm em horário de funcionamento).
        """
        self._marcar_processado(c)
        if not self.aberta:
            return None
        aptos = [v for v in self.patio.values() if v.rank >= c.rank and v.soc >= v.alvo - EPS]
        if not aptos:
            return None
        return min(aptos, key=lambda v: (v.rank - c.rank, v.soc, v.plugado, v.id))

    def ordenar_fila(self, t: float) -> None:
        """Ordena `self.fila` pela política (`self.pol['prioridade']`). Regulamento 6.3.3.

        Chamar a cada tentativa de plugar. Último desempate sempre o menor `id`.
        - `chegada`: FIFO por `entrou_fila_t` (os carros da fila em T0 entram todos no mesmo instante).
        - `menor_soc`: menor autonomia restante em km (`autonomia_km * soc / 100`) primeiro; km, não SOC.
        - `proxima_retirada`: primeiro quem tem a próxima reserva compatível mais cedo = primeiro contrato
          ainda não retirado, em ordem de horário, com categoria <= a do carro; sem reserva vai para o fim.
          Empate: maior SOC, depois menor `id`.
        Ex. 6.3.3: A(Bronze 30%, 55.5 km), B(Prata 20%, 56.0 km), C(Ouro 55%), D(Diamante 40%) ->
        menor_soc A,B,D,C; chegada A,B,C,D; proxima_retirada C,D,B,A.
        """
        self.fila.sort(key=self._chave_prioridade)

    def escolher_ponto(self, v: Veiculo) -> Optional[Ponto]:
        """Em qual carregador v pluga (6.3.4), ou None se não houver saída livre.

        Entre os pontos em operação (`not quebrado`) com saída livre, o que daria MAIS potência a v:
        potência nominal do carregador dividida igualmente entre v e quem já está ali, cada um limitado
        pela sua curva (`potencia.potencia_curva`, AC/DC conforme o carregador). Ignora o limite da agência
        e a `divisao`. Empate: o primeiro de `self.pontos` (ordem alfabética do id).
        Ex.: DC-60 com um Geely 30% e AC-22 vazio; chega Dolphin GS 20%: no DC-60 teria 60/2 = 30 kW,
        no AC-22 só 7 kW -> DC-60.
        """
        melhor, melhor_kw = None, -1.0
        for ponto in self.pontos:
            if ponto.quebrado or ponto.livres <= 0:
                continue
            kw = self._estimar_no_ponto(v, ponto)
            if kw > melhor_kw + EPS:
                melhor, melhor_kw = ponto, kw
        return melhor

    def _estimar_no_ponto(self, v: Veiculo, ponto: Ponto) -> float:
        """Potência estimada de v em `ponto` (6.3.4): nominal dividida igualmente entre v e quem já está
        ali, com teto na curva. ESTIMATIVA_PONTO escolhe a leitura da regra (conferir com o juiz)."""
        n = len(ponto.conectados) + 1
        if ESTIMATIVA_PONTO == "agua":
            caps = [self._curva(u, ponto) for u in ponto.conectados] + [self._curva(v, ponto)]
            return potencia.enchimento_agua(ponto.modelo.potencia_kw, caps)[-1]
        return min(ponto.modelo.potencia_kw / n, self._curva(v, ponto))

    def plugar_fila(self, t: float) -> None:
        """Pluga a fila (5.2, 6.3.3): só com a agência aberta, na ordem da fila, enquanto houver saída livre.

        Ordene (`ordenar_fila`), escolha o ponto (`escolher_ponto`), conecte (`plugar`) e recalcule as
        potências. Chamar quando um carro volta, termina a recarga, a agência abre ou um carregador volta.
        Respeite plugados <= saídas (`checar_ocupacao`).
        """
        if not self.aberta or not self.fila:
            return
        self.ordenar_fila(t)
        mudou = False
        for v in list(self.fila):
            ponto = self.escolher_ponto(v)
            if ponto is None:
                break  # nenhuma saída livre em carregador em operação
            self.plugar(v, ponto)
            mudou = True
        if mudou:
            self.checar_ocupacao()
            self.recalcular_potencias(t)

    def recalcular_potencias(self, t: float) -> None:
        """Define `v.potencia_kw` de cada plugado (5.3, 6.3.5) e reagenda os fins de degrau.

        Recalcular a cada mudança: carro pluga/despluga, troca de degrau, início/fim da ponta, evento.
        Carro quebrado/em ponta com `evitar_ponta` -> 0 kW (continua plugado). Carro com SOC >= alvo -> 0.
        Camada 1: dentro de cada carregador, a potência nominal vai para os carros que ainda carregam,
        com teto na curva do carro (`potencia.potencia_curva`). Camada 2: o limite da agência
        (`self.limite_kw`) é repartido, e o que cada carro recebeu na camada 1 é o seu máximo.
        `divisao`: `igual` -> `potencia.enchimento_agua`; `prioridade` -> `potencia.sequencial` na ordem
        da `prioridade` (ordenar a lista de plugados pela mesma regra da fila).
        Ex. 6.3.5 (limite 40.5, 2x DC-60, Kwid 26.6, Geely 71.5, JAC 16.45, Dolphin GS 47.75):
        igual -> 10.125 kW para cada um; prioridade (menor_soc) -> Kwid 26.6, Geely 13.9, JAC 0, Dolphin 0.
        Com limite 80: igual -> JAC 16.45 e os outros 21.18333; prioridade -> Kwid 26.6, Geely 53.4, demais 0.
        Depois chame `agendar_fim_degrau` para cada carro.
        """
        seq = self.pol["divisao"] == "prioridade"
        reparte = potencia.sequencial if seq else potencia.enchimento_agua
        pausado = self.em_ponta  # só fica True com evitar_ponta (5.3, 6.3.6)
        plugados, ativos, cap1 = [], [], {}
        for ponto in self.pontos:
            for v in ponto.conectados:
                plugados.append(v)
                v.potencia_kw = 0.0
            if ponto.quebrado or pausado:
                continue
            carregando = [v for v in ponto.conectados if v.soc < v.alvo - EPS]
            if not carregando:
                continue
            if seq:
                carregando.sort(key=self._chave_prioridade)
            # camada 1: potência nominal do carregador entre os carros que ainda carregam
            for v, kw in zip(carregando, reparte(ponto.modelo.potencia_kw, [self._curva(v, ponto) for v in carregando])):
                cap1[v.id] = kw
                ativos.append(v)
        # camada 2: limite da agência (kW útil em B3 ou demanda contratada em A4/SE)
        if ativos:
            if seq:
                ativos.sort(key=self._chave_prioridade)
            for v, kw in zip(ativos, reparte(self.limite_kw, [cap1[v.id] for v in ativos])):
                v.potencia_kw = max(0.0, kw)
        for v in plugados:
            self.agendar_fim_degrau(v, t)

    def agendar_fim_degrau(self, v: Veiculo, t: float) -> None:
        """Agenda 'fim_recarga' para quando v chega ao próximo degrau de 5% ou ao alvo (5.3, 6.3.2).

        A potência é constante dentro do degrau [5i, 5i+5). Próximo limite = min(alvo, (i+1)*5) com
        i = int(soc/5 + 1e-9). Tempo = (limite - soc)/100 * bateria_kwh / potencia_kw * 60 min.
        Defina `v.soc_limite` = esse limite, incremente `v.token` (invalida agendamentos antigos) e use
        `self.agendar(t + dt, PRIO_FIM_RECARGA, 'fim_recarga', v.id, v.token)`. Potência 0 -> não agende.
        Ex. 6.3.2: Dolphin GS (44.9 kWh) de 20% a 80% sozinho num DC-60 leva 36,7 min.
        """
        v.token += 1  # invalida o fim de degrau agendado com a potência antiga
        if v.soc >= v.alvo - EPS:
            v.soc_limite = None
            return
        i = int(v.soc / 5 + 1e-9)
        limite = min(v.alvo, (i + 1) * 5.0)
        v.soc_limite = limite
        if v.potencia_kw <= EPS:
            return
        dt = (limite - v.soc) / 100.0 * v.modelo.bateria_kwh / v.potencia_kw * 60.0
        self.agendar(t + dt, PRIO_FIM_RECARGA, "fim_recarga", v.id, v.token)

    def on_fim_recarga(self, vid: str, token: int, t: float) -> None:
        """Chegou ao fim do degrau. Ignore se `token` != `v.token` (agendamento velho).

        Ao atingir o alvo (80%): desplugar se a agência estiver aberta; se fechada, segura a saída até
        a abertura (5.2). Depois tente plugar a fila (`plugar_fila`) e recalcule as potências.
        """
        v = self.veiculos[vid]
        if token != v.token or not v.plugado:
            return
        if v.soc_limite is not None:
            v.soc = max(v.soc, v.soc_limite)  # fim exato do degrau (remove resíduo de ponto flutuante)
        if v.soc >= v.alvo - EPS:
            v.soc = max(v.soc, v.alvo)
            if self.aberta:
                self.desplugar(v)
                self.plugar_fila(t)
                self._registrar_fila("fim80")
            # fechada: segura a saída até a abertura (5.2)
        self.recalcular_potencias(t)

    def on_devolucao(self, vid: str, soc: float, t: float) -> None:
        """Carro volta do contrato com `soc` e entra no pátio. Um carro devolvido apto pode sair no mesmo minuto (5.1)."""
        v = self.veiculos[vid]
        v.soc = soc
        v.plugado, v.carregador, v.potencia_kw, v.soc_limite = False, None, 0.0, None
        v.na_fila, v.entrou_fila_t = False, None
        self.entrar_patio(v, t)

    def on_abertura(self, t: float) -> None:
        """Agência abre. Com ela aberta, plugar e desplugar voltam a valer (5.2).

        Desplugue quem está parado no alvo (80%) segurando saída, depois `plugar_fila`.
        """
        self.aberta = True
        for ponto in self.pontos:
            for v in list(ponto.conectados):
                if v.soc >= v.alvo - EPS:
                    self.desplugar(v)
        self.plugar_fila(t)
        self.recalcular_potencias(t)
        self._registrar_fila("abertura")

    def on_fechamento(self, t: float) -> None:
        """Agência fecha: ninguém retira nem pluga/despluga; a recarga continua (5.2).

        Quem atinge 80% com a agência fechada segura a saída até a abertura.
        """
        self.aberta = False  # a recarga continua; nada é plugado ou desplugado até abrir
        self._registrar_fila("fechamento")

    def on_ponta(self, inicio: bool, t: float) -> None:
        """Início/fim da ponta (seg-sex 18:00-21:00) com `evitar_ponta` (5.3, 6.3.6).

        Na ponta todos a 0 kW, continuam plugados e plugar continua permitido. Recalcule as potências.
        """
        self.em_ponta = inicio
        self.recalcular_potencias(t)

    def agendar_eventos(self, eventos) -> None:
        """Agenda os eventos ao vivo (seção 11). `eventos`: lista de `params` (minutos desde 17/10/2049 00:00).

        O significado e o formato de `params` são explicados no anúncio de cada evento; vêm de
        `eventos_ativos` de GET /status. Ex. de uso: `self.agendar(t, PRIO_ABERTURA, 'evento', params)`.
        """
        self._limites_ativos: dict = {}
        for n, params in enumerate(eventos):
            ev = interpretar_evento(params)
            if ev is None:
                self.violar(f"evento não reconhecido (ajustar interpretar_evento): {params!r}")
                continue
            tipo, ini, fim, valor = ev
            self.agendar(max(ini, tempo.T0), PRIO_ABERTURA, "evento", n, tipo, True, valor)
            if fim is not None:
                self.agendar(max(fim, tempo.T0), PRIO_ABERTURA, "evento", n, tipo, False, valor)

    def on_evento(self, t: float, *params) -> None:
        """Aplica um evento no instante t (ex.: limite da concessionária, carregador fora de operação).

        Recalcule as potências; ao voltar um carregador, tente plugar a fila (6.3.3).
        """
        n, tipo, inicio, valor = params
        if tipo == "limite":
            if inicio:
                self._limites_ativos[n] = float(valor)
            else:
                self._limites_ativos.pop(n, None)
            self.limite_kw = min([self.limite_base_kw, *self._limites_ativos.values()])
            self.recalcular_potencias(t)
        elif tipo == "carregador":
            alvos = [p for p in self.pontos if p.id == valor] or [p for p in self.pontos if p.modelo.id == valor][:1]
            for ponto in alvos:
                ponto.quebrado = inicio
                if inicio and EVENTO_QUEBRA_DESPLUGA:
                    for v in list(ponto.conectados):
                        self.desplugar(v)
                        v.na_fila = True
                        self.fila.append(v)
            if not inicio:
                self.plugar_fila(t)  # carregador voltou: tenta plugar (6.3.3)
            self.recalcular_potencias(t)


def interpretar_evento(params):
    """Traduz os `params` de um evento (GET /status, eventos_ativos) em (tipo, ini, fim, valor).

    HIPÓTESE até o anúncio oficial: [tipo, agencia, inicio_min, fim_min, valor], com
    tipo "limite" (valor = kW máximo da agência) ou "carregador" (valor = id do ponto, ex. "dc_60x2-0",
    ou modelo_id, que derruba a primeira unidade). Também aceita dict com essas chaves.
    Quando o formato real for anunciado, ajustar SÓ esta função. Retorna None se não reconhecer.
    """
    if isinstance(params, dict):
        params = [params.get("tipo"), params.get("agencia"), params.get("inicio"), params.get("fim"),
                  params.get("valor")]
    if not isinstance(params, (list, tuple)) or len(params) < 5:
        return None
    tipo, _ag, ini, fim, valor = params[:5]
    if tipo not in ("limite", "carregador"):
        return None
    return tipo, float(ini), (None if fim is None else float(fim)), valor


def simular(cenario: Cenario, sub_normalizada: dict, eventos=()) -> Resultado:
    return Motor(cenario, sub_normalizada, eventos).rodar()
