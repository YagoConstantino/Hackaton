"""Testes do motor (etapas 2-7) com os números do regulamento. python -m unittest discover -s testes"""
import copy
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, motor, tempo, validar  # noqa: E402
from kickoff.modelo import Agencia, Contrato, VeiculoT0  # noqa: E402

DADOS = RAIZ / "dados"
TEM_BANGKOK = (DADOS / "Bangkok").is_dir()
SEG = tempo.DIA  # segunda 18/10/2049 00:00


def h(dia_min, hora, minuto=0):
    return dia_min + hora * 60 + minuto


def cenario_base():
    """Catálogo real (modelos, curvas, carregadores, entradas) com agência e frota vazias."""
    cen = copy.deepcopy(dados.carregar(DADOS, "Bangkok"))
    cen.agencia = Agencia("Teste", 6, 0, [(0, 1440)] * 7, "a4_150")
    cen.veiculos, cen.contratos = [], []
    return cen


def sub(cen, carregadores, entrada="a4_150", demanda=130, **pol):
    s = {"agencia": cen.agencia.nome, "carregadores": carregadores, "entrada": entrada, "politica": pol}
    if entrada not in ("b3_45", "b3_75"):
        s["demanda_contratada_kw"] = demanda
    assert validar.validar(s, cen) == [], validar.validar(s, cen)
    return validar.normalizar(s, cen)


def veiculo(m, vid, modelo, soc, plugado_em=None):
    v = motor.Veiculo(vid, m.cen.modelos[modelo], m.cen.modelos[modelo].rank, soc)
    m.veiculos[vid] = v
    m.patio[vid] = v
    if plugado_em is not None:
        m.plugar(v, plugado_em)
    return v


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Etapa2(unittest.TestCase):
    def setUp(self):
        self.cen = cenario_base()
        self.m = motor.Motor(self.cen, sub(self.cen, {"ac_7": 1}))
        self.m.aberta = True

    def test_soc_devolucao_e_teto(self):  # 4.1
        v = veiculo(self.m, "V1", "Geely EX2 Pro", 80.0)
        c = Contrato("C1", "Prata", 2, 0, 100, 0, 144.5)
        self.assertAlmostEqual(self.m.soc_devolucao(v, c), 144.5 / 289 * 100)
        c.km_devolucao = 289.0  # 100% pela autonomia, mas saiu com 80%
        self.assertEqual(self.m.soc_devolucao(v, c), 80.0)

    def test_escolha_6_3_1(self):
        m = self.m
        geely = veiculo(m, "V1", "Geely EX2 Pro", 82)
        mini = veiculo(m, "V2", "BYD Dolphin Mini GS", 95, plugado_em=m.pontos[0])
        mg4 = veiculo(m, "V3", "MG4 Urban Comfort", 100)
        veiculo(m, "V4", "JAC E-JS1", 100)
        c = Contrato("C1", "Prata", 2, h(SEG, 10), None, 0, None)
        self.assertIs(m.escolher_carro(c, c.retirada_t), geely)
        geely.soc = 78
        self.assertIs(m.escolher_carro(c, c.retirada_t), mini)
        mini.soc = 70
        self.assertIs(m.escolher_carro(c, c.retirada_t), mg4)

    def test_desempate_por_id(self):
        m = self.m
        veiculo(m, "V9", "Geely EX2 Pro", 80)
        a = veiculo(m, "V2", "BYD Dolphin Mini GS", 80)
        self.assertIs(m.escolher_carro(Contrato("C", "Prata", 2, 0, None, 0, None), 0), a)

    def test_fechada_nao_retira(self):
        veiculo(self.m, "V1", "Geely EX2 Pro", 90)
        self.m.aberta = False
        self.assertIsNone(self.m.escolher_carro(Contrato("C", "Prata", 2, 0, None, 0, None), 0))


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Etapa3e6Fila(unittest.TestCase):
    """6.3.3: A(Kwid 30%), B(Dolphin Mini 20%), C(MG4 55%), D(Leapmotor 40%)."""

    def ordem(self, prioridade):
        cen = cenario_base()
        cen.contratos = [
            Contrato("K1", "Ouro", 3, h(SEG, 12, 30), None, 0, None),
            Contrato("K2", "Prata", 2, h(SEG, 13, 15), None, 0, None),
            Contrato("K3", "Bronze", 1, h(SEG, 14), None, 0, None),
        ]
        m = motor.Motor(cen, sub(cen, {"ac_7": 1}, prioridade=prioridade))
        for vid, mod, soc, t in (("A", "Renault Kwid E-Tech", 30, (10, 0)), ("B", "BYD Dolphin Mini GS", 20, (10, 20)),
                                 ("C", "MG4 Urban Comfort", 55, (10, 40)), ("D", "Leapmotor B10 BEV", 40, (10, 55))):
            v = veiculo(m, vid, mod, soc)
            v.na_fila, v.entrou_fila_t = True, h(SEG, *t)
            m.fila.append(v)
        m.ordenar_fila(h(SEG, 11))
        return [v.id for v in m.fila]

    def test_menor_soc(self):
        self.assertEqual(self.ordem("menor_soc"), list("ABDC"))

    def test_chegada(self):
        self.assertEqual(self.ordem("chegada"), list("ABCD"))

    def test_proxima_retirada(self):
        self.assertEqual(self.ordem("proxima_retirada"), list("CDBA"))


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Etapa3Ponto(unittest.TestCase):
    def test_6_3_4(self):
        cen = cenario_base()
        m = motor.Motor(cen, sub(cen, {"dc_60x2": 1, "ac_22x2": 1}))
        dc = next(p for p in m.pontos if p.modelo.id == "dc_60x2")
        ac = next(p for p in m.pontos if p.modelo.id == "ac_22x2")
        veiculo(m, "G", "Geely EX2 Pro", 30, plugado_em=dc)
        d = veiculo(m, "D", "BYD Dolphin GS", 20)
        self.assertIs(m.escolher_ponto(d), dc)
        m.plugar(d, dc)
        self.assertIs(m.escolher_ponto(veiculo(m, "X", "BYD Dolphin GS", 20)), ac)


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Etapa4Potencia(unittest.TestCase):
    """6.3.5: 2x DC-60; Geely 30% + Dolphin GS 50% no 1; Kwid 40% + JAC 75% no 2."""

    def potencias(self, limite, divisao):
        cen = cenario_base()
        s = sub(cen, {"dc_60x2": 2}, demanda=130, prioridade="menor_soc", divisao=divisao)
        m = motor.Motor(cen, s)
        m.limite_kw = limite
        p1, p2 = m.pontos
        vs = {"geely": veiculo(m, "V1", "Geely EX2 Pro", 30, p1), "dolphin": veiculo(m, "V2", "BYD Dolphin GS", 50, p1),
              "kwid": veiculo(m, "V3", "Renault Kwid E-Tech", 40, p2), "jac": veiculo(m, "V4", "JAC E-JS1", 75, p2)}
        m.recalcular_potencias(0)
        return {k: v.potencia_kw for k, v in vs.items()}

    def check(self, got, exp):
        for k, x in exp.items():
            self.assertAlmostEqual(got[k], x, places=4, msg=k)

    def test_igual_40_5(self):
        self.check(self.potencias(40.5, "igual"), dict(geely=10.125, dolphin=10.125, kwid=10.125, jac=10.125))

    def test_prioridade_40_5(self):
        self.check(self.potencias(40.5, "prioridade"), dict(kwid=26.6, geely=13.9, jac=0, dolphin=0))

    def test_igual_80(self):
        x = (80 - 16.45) / 3
        self.check(self.potencias(80, "igual"), dict(geely=x, dolphin=x, kwid=x, jac=16.45))

    def test_prioridade_80(self):
        self.check(self.potencias(80, "prioridade"), dict(kwid=26.6, geely=53.4, jac=0, dolphin=0))


def rodar_um_carro(modelo, soc, carregador, inicio, evitar=False):
    """Agência 24h, um carro no estoque a `soc`, plugado em T0... devolvido em `inicio`."""
    cen = cenario_base()
    cen.veiculos = [VeiculoT0("V1", modelo, cen.modelos[modelo].categoria, cen.modelos[modelo].rank,
                              "em_contrato", soc, inicio, soc)]
    s = sub(cen, {carregador: 1}, evitar_ponta=evitar)
    m = motor.Motor(cen, s)
    fins = []
    orig = m.on_fim_recarga

    def espiao(vid, token, t):
        orig(vid, token, t)
        if m.veiculos[vid].soc >= 80 - 1e-9 and not fins:
            fins.append(t)
    m.on_fim_recarga = espiao
    res = m.rodar()
    return fins[0], res


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Etapa3Recarga(unittest.TestCase):
    def test_6_3_2_dolphin_dc60(self):
        t0 = h(SEG, 10)
        fim, _ = rodar_um_carro("BYD Dolphin GS", 20, "dc_60x2", t0)
        self.assertAlmostEqual(fim - t0, 36.7, places=1)


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Etapa5Ponta(unittest.TestCase):
    """6.3.6: MG4 pluga seg 17:00 num AC-22 a 11 kW, 29% -> 80% (~22 kWh, 2 h)."""

    def test_sem_evitar(self):
        fim, res = rodar_um_carro("MG4 Urban Comfort", 29, "ac_22x2", h(SEG, 17))
        self.assertAlmostEqual(fim, h(SEG, 19), delta=1)
        ponta = sum(e for i, e in res.bins.items() if tempo.eh_ponta(15 * i))
        self.assertAlmostEqual(ponta, 11, delta=0.2)

    def test_com_evitar(self):
        fim, res = rodar_um_carro("MG4 Urban Comfort", 29, "ac_22x2", h(SEG, 17), evitar=True)
        self.assertAlmostEqual(fim, h(SEG, 22), delta=1)
        ponta = sum(e for i, e in res.bins.items() if tempo.eh_ponta(15 * i))
        self.assertAlmostEqual(ponta, 0, places=6)


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Invariantes(unittest.TestCase):
    """Rodada completa de Bangkok em vários regimes: regras 5.1-5.3 nunca violadas."""

    SUBS = [
        ({"ac_7": 2, "dc_30": 1}, "b3_45", None, dict(prioridade="menor_soc")),
        ({"dc_60x2": 2, "ac_7": 2}, "b3_45", None, dict(prioridade="proxima_retirada", divisao="prioridade")),
        ({"ac_22x2": 3}, "b3_75", None, dict(prioridade="chegada", evitar_ponta=True)),
        ({"dc_120x2": 1, "dc_30": 2, "ac_11": 2}, "a4_150", 60, dict(prioridade="menor_soc", divisao="prioridade")),
    ]

    def test_regras(self):
        cen0 = dados.carregar(DADOS, "Bangkok")
        for car, ent, dem, pol in self.SUBS:
            s = {"agencia": "Bangkok", "carregadores": car, "entrada": ent, "politica": pol}
            if dem:
                s["demanda_contratada_kw"] = dem
            self.assertEqual(validar.validar(s, cen0), [])
            sn = validar.normalizar(s, cen0)
            m = motor.Motor(cen0, sn)
            erros = []
            plug, desp = m.plugar, m.desplugar

            def plugar(v, p, m=m):
                if not m.aberta:
                    erros.append(f"plugou fechada {tempo.texto(m.t)}")
                plug(v, p)

            def desplugar(v, m=m):
                if not m.aberta:
                    erros.append(f"desplugou fechada {tempo.texto(m.t)}")
                desp(v)
            m.plugar, m.desplugar = plugar, desplugar
            orig_rec = m.recalcular_potencias

            def rec(t, m=m):
                orig_rec(t)
                tot = sum(v.potencia_kw for p in m.pontos for v in p.conectados)
                if tot > m.limite_kw + 1e-6:
                    erros.append(f"{tot:.3f} kW > limite {m.limite_kw}")
                if any(v.soc > 80 + 1e-6 and v.potencia_kw > 0 for p in m.pontos for v in p.conectados):
                    erros.append("carregando acima de 80%")
            m.recalcular_potencias = rec
            res = m.rodar()
            self.assertEqual(res.violacoes, [], (car, pol))
            self.assertEqual(erros[:5], [], (car, pol))
            for r in res.retiradas:
                self.assertGreaterEqual(r.soc, 80 - 1e-9)
                self.assertGreaterEqual(r.rank_entregue, r.rank_pedido)
            n = len(res.retiradas) + len(res.nao_atendidos)
            self.assertEqual(n, len(cen0.contratos))


@unittest.skipUnless(TEM_BANGKOK, "dados/Bangkok ausentes")
class Etapa7Eventos(unittest.TestCase):
    def test_limite_e_quebra(self):
        cen = dados.carregar(DADOS, "Bangkok")
        s = validar.normalizar({"agencia": "Bangkok", "carregadores": {"ac_7": 2, "dc_30": 1}, "entrada": "b3_45"}, cen)
        ini, fim = h(SEG, 8), h(SEG, 18)
        res = motor.simular(cen, s, [["limite", "Bangkok", ini, fim, 10]])
        self.assertEqual(res.violacoes, [])
        janelas = [e * 4 for i, e in res.bins.items() if ini <= 15 * i < fim - 15]
        self.assertLessEqual(max(janelas), 10 + 1e-6)
        res2 = motor.simular(cen, s, [["carregador", "Bangkok", ini, fim, "dc_30"]])
        self.assertEqual(res2.violacoes, [])
        self.assertLess(max(e * 4 for i, e in res2.bins.items() if ini <= 15 * i < fim - 15), 14 + 1e-6)


if __name__ == "__main__":
    unittest.main()
