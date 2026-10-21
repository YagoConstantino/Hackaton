"""Testes dos números do regulamento. python -m unittest discover -s testes"""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from kickoff import dados, potencia, validar  # noqa: E402
from kickoff.modelo import Agencia, Carregador, Cenario, Entrada, ModeloVeiculo  # noqa: E402

# curva DC no degrau (ex. 6.3.5): ordem de prioridade Kwid, Geely, JAC, Dolphin GS
KWID, GEELY, JAC, DOLPHIN = 26.6, 71.5, 16.45, 47.75


def _aprox(t, a, b, casas=4):
    t.assertEqual(len(a), len(b))
    for x, y in zip(a, b):
        t.assertAlmostEqual(x, y, places=casas)


class Divisao(unittest.TestCase):
    def test_igual_limite_40_5(self):
        c1 = potencia.enchimento_agua(60, [GEELY, DOLPHIN]) + potencia.enchimento_agua(60, [KWID, JAC])
        _aprox(self, c1, [30, 30, 26.6, 16.45])
        _aprox(self, potencia.enchimento_agua(40.5, c1), [10.125] * 4)

    def test_prioridade_limite_40_5(self):
        # ordem menor_soc: Kwid, Geely, JAC, Dolphin
        c1 = {
            "geely": potencia.sequencial(60, [GEELY, DOLPHIN])[0],
            "dolphin": potencia.sequencial(60, [GEELY, DOLPHIN])[1],
            "kwid": potencia.sequencial(60, [KWID, JAC])[0],
            "jac": potencia.sequencial(60, [KWID, JAC])[1],
        }
        self.assertEqual(c1["geely"], 60)
        self.assertEqual(c1["dolphin"], 0)
        ordem = [c1["kwid"], c1["geely"], c1["jac"], c1["dolphin"]]
        _aprox(self, potencia.sequencial(40.5, ordem), [26.6, 13.9, 0, 0])

    def test_igual_limite_80(self):
        c1 = [30, 30, 26.6, 16.45]
        _aprox(self, potencia.enchimento_agua(80, c1), [21.18333333, 21.18333333, 21.18333333, 16.45])

    def test_prioridade_limite_80(self):
        ordem = [26.6, 60, 16.45, 0]
        _aprox(self, potencia.sequencial(80, ordem), [26.6, 53.4, 0, 0])


def _cenario(kva=150, kw_util=135.0, existente="a4_150"):
    ag = Agencia("Teste", 6, 10, [(0, 1440)] * 7, existente)
    ents = {
        "b3_45": Entrada("b3_45", "B3 45 kVA", 45, 40.5),
        "a4_150": Entrada("a4_150", "A4 em poste 150 kVA", 150, 135.0),
    }
    car = {"ac_7": Carregador("ac_7", "AC-7", "AC", 7, 1)}
    return Cenario(ag, {}, [], [], car, ents, {})


class Demanda(unittest.TestCase):
    def test_arredondamento(self):
        for entra, sai in ((84, 80), (85, 90), (75, 80), (87.3, 90)):
            self.assertEqual(validar.arredondar_demanda(entra), sai)

    def test_teto_a4_150(self):
        self.assertEqual(validar.teto_demanda(_cenario().entradas["a4_150"]), 130)

    def test_135_rejeitado_no_a4_150(self):
        sub = {"agencia": "Teste", "carregadores": {"ac_7": 1}, "entrada": "a4_150", "demanda_contratada_kw": 135}
        erros = validar.validar(sub, _cenario())
        self.assertEqual(len(erros), 1)
        self.assertIn("arredondado para 140", erros[0])

    def test_84_aceito_e_omitida_vale_teto(self):
        cen = _cenario()
        sub = {"agencia": "Teste", "carregadores": {"ac_7": 1}, "entrada": "a4_150", "demanda_contratada_kw": 84}
        self.assertEqual(validar.validar(sub, cen), [])
        self.assertEqual(validar.demanda_kw(sub, cen), 80)
        del sub["demanda_contratada_kw"]
        self.assertEqual(validar.demanda_kw(sub, cen), 130)

    def test_b3_rejeita_demanda(self):
        cen = _cenario(existente="b3_45")
        sub = {"agencia": "Teste", "carregadores": {"ac_7": 1}, "entrada": "b3_45", "demanda_contratada_kw": 40}
        self.assertEqual(len(validar.validar(sub, cen)), 1)


class Curva(unittest.TestCase):
    def test_indice_do_degrau(self):
        m = ModeloVeiculo("X", "Ouro", 2, 40, 300, 7, 60, list(range(20)), [float(i) for i in range(100, 120)])
        self.assertEqual(potencia.potencia_curva(m, 79.99, "AC"), 15)
        self.assertEqual(potencia.potencia_curva(m, 100, "AC"), 19)
        self.assertEqual(potencia.potencia_curva(m, 0, "DC"), 100)
        self.assertEqual(potencia.potencia_curva(m, 100, "DC"), 119)


@unittest.skipUnless((RAIZ / "dados" / "Bangkok").is_dir(), "dados/Bangkok ausentes")
class Dados(unittest.TestCase):
    def test_carregar_bangkok(self):
        cen = dados.carregar(RAIZ / "dados", "Bangkok")
        self.assertEqual(cen.agencia.entrada_existente, "b3_45")
        self.assertTrue(cen.contratos)
        m = cen.modelos["BYD Dolphin GS"]
        self.assertEqual(len(m.curva_dc), 20)
        self.assertEqual(len(m.curva_ac), 20)
        # degrau 16 (80-85%) = média das linhas 16 e 17 da tabela (24.8 e 19.4)
        self.assertAlmostEqual(m.curva_dc[16], 22.1, places=6)


if __name__ == "__main__":
    unittest.main()
