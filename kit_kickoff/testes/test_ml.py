"""Testes do pipeline de ML (ml/). Rodam em TODAS as agências de dados/ e numa agência sintética.

  python3 -m unittest testes.test_ml -v
Exige numpy, pandas e scikit-learn (pip install -r ml/requirements.txt); sem eles, os testes são pulados.
"""
import shutil
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    import numpy as np
    import sklearn  # noqa: F401
    from ml import carregadores as C
    from ml import energia as E
    from ml import features as F
    from ml import nao_supervisionado as U
    from ml import sintetico as S
    TEM_ML = True
except ImportError:
    TEM_ML = False

from kickoff import tempo, validar  # noqa: E402

DADOS = RAIZ / "dados"
AGENCIAS = sorted(p.name for p in DADOS.iterdir() if (p / "contratos_publicos.csv").exists()) if DADOS.is_dir() else []
BASE = "Bangkok" if "Bangkok" in AGENCIAS else (AGENCIAS[0] if AGENCIAS else None)
warnings.filterwarnings("ignore")


def setUpModule():
    if not TEM_ML:
        raise unittest.SkipTest("numpy/pandas/scikit-learn ausentes")
    if BASE is None:
        raise unittest.SkipTest("nenhuma agência em dados/")


class Curvas(unittest.TestCase):
    def test_tempo_regulamento_6_3_2(self):
        cen = F.carregar(BASE)
        if "BYD Dolphin GS" not in cen.modelos:
            self.skipTest("modelo do exemplo ausente")
        self.assertAlmostEqual(F.tempo_recarga(cen.modelos["BYD Dolphin GS"], 20, 80, 60, "DC"), 36.7, places=1)

    def test_tabela_modelos_todas_agencias(self):
        for ag in AGENCIAS:
            with self.subTest(ag=ag):
                cen = F.carregar(ag)
                tm = F.tabela_modelos(cen)
                self.assertEqual(len(tm), len(cen.modelos))
                self.assertFalse(tm.isna().any().any())
                self.assertEqual(tm.frota_n.sum(), len(cen.veiculos))

    def test_carregador_suficiente_coerente(self):
        """Modelo cujo DC não passa do menor DC do catálogo não precisa de nada maior."""
        for ag in AGENCIAS:
            cen = F.carregar(ag)
            dcs = sorted((c for c in cen.carregadores.values() if c.tipo == "DC"), key=lambda c: c.potencia_kw)
            if not dcs:
                continue
            for m in cen.modelos.values():
                if max(m.curva_dc[:16]) <= dcs[0].potencia_kw / dcs[0].saidas:
                    with self.subTest(ag=ag, modelo=m.modelo):
                        self.assertEqual(F.carregador_suficiente(cen, m), dcs[0].id)


class EnergiaFecha(unittest.TestCase):
    """A soma do kWh das sessões (rótulos) = energia total medida pelo motor."""

    def test_todas_agencias(self):
        for ag in AGENCIAS:
            with self.subTest(ag=ag):
                cen = F.carregar(ag)
                res = F.simular(cen)
                s = F.sessoes_energia(cen, res)
                total = sum(res.bins.values())
                self.assertAlmostEqual(s.kwh.sum(), total, delta=max(1e-6, 1e-6 * total))
                self.assertTrue((s.kwh >= 0).all())


class AgenciaSintetica(unittest.TestCase):
    """Pipeline inteiro numa agência 24 h, 4 vagas, criada numa pasta temporária."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(DADOS / BASE, cls.tmp / BASE)
        S.criar(BASE, "Sint", escala=2, vagas=4, horario="24h", seed=1, dados_dir=cls.tmp)
        cls.cen = F.carregar("Sint", cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_ficha_reflete_horario(self):
        fi = F.ficha_agencia(self.cen)
        self.assertTrue(fi["aberta_24h"])
        self.assertTrue(fi["aberta_na_ponta"])
        self.assertFalse(fi["fecha_ate_18h"])
        self.assertEqual(fi["vagas"], 4)
        self.assertEqual(set(fi["folga_por_rank"]), set(self.cen.categorias.values()))

    def test_contratos_dobrados_e_em_horario(self):
        base = F.carregar(BASE, self.tmp)
        self.assertEqual(len(self.cen.contratos), 2 * len(base.contratos))
        self.assertTrue(all(tempo.aberta(self.cen.agencia, c.retirada_t) for c in self.cen.contratos))

    def test_energia_fecha(self):
        res = F.simular(self.cen)
        self.assertAlmostEqual(F.sessoes_energia(self.cen, res).kwh.sum(), sum(res.bins.values()), places=3)

    def test_combos_4_vagas(self):
        cs = C.combos(self.cen)
        self.assertTrue(all(sum(self.cen.carregadores[k].saidas * n for k, n in c.items()) <= 4 for c in cs))
        sub = {"agencia": "Sint", "entrada": self.cen.agencia.entrada_existente}
        self.assertTrue(all(validar.validar({**sub, "carregadores": c}, self.cen) == [] for c in cs))

    def test_surrogate_e_recomendacao(self):
        df = C.gerar_dataset(self.cen, n=24, seed=0, workers=1)
        mods = C.treinar(df, n_imp=0)
        self.assertTrue(all(np.isfinite(i["MAE_cv"]) for i in mods.values()))
        rec = C.recomendar(self.cen, mods, top=3, workers=1)
        self.assertEqual(len(rec), 3)
        for s in rec.submissao:
            self.assertEqual(validar.validar(s, self.cen), [])
        # ordenado pelos números reais
        self.assertTrue(list(rec.nao_atendidos) == sorted(rec.nao_atendidos))


class Reamostragem(unittest.TestCase):
    def test_semanas_inteiras(self):
        cen = F.carregar(BASE)
        sem = 7 * tempo.DIA
        orig = {(c.retirada_t - tempo.T0) % sem for c in cen.contratos}
        for seed in (1, 2, 3):
            r = S.reamostrar_semanas(cen, seed)
            self.assertTrue(all((c.retirada_t - tempo.T0) % sem in orig for c in r.contratos))
            self.assertTrue(all(tempo.T0 <= c.retirada_t < tempo.T0 + 4 * sem for c in r.contratos))
            self.assertIsNot(r.contratos, cen.contratos)
        self.assertEqual(len(cen.contratos), len(F.carregar(BASE).contratos))  # original intacto


class NaoSupervisionado(unittest.TestCase):
    def test_curvas_reprodutivel(self):
        cen = F.carregar(BASE)
        a, _ = U.agrupar_modelos(cen)
        b, _ = U.agrupar_modelos(cen)
        self.assertEqual(list(a.classe_recarga), list(b.classe_recarga))
        self.assertEqual(len(a), len(cen.modelos))
        if len(cen.modelos) >= 3:
            self.assertGreaterEqual(a.classe_recarga.nunique(), 2)

    def test_segmentos_dias_anomalias(self):
        cen = F.carregar(BASE)
        ct = F.tabela_contratos(cen)
        d, perf, info = U.agrupar_contratos(ct)
        self.assertEqual(perf.contratos.sum(), len(d))
        dd, pd_, _ = U.agrupar_dias(F.tabela_dias(cen))
        self.assertEqual(pd_.dias.sum(), len(dd))
        an = U.anomalias(ct, 0.03)
        self.assertLessEqual(len(an), int(0.05 * len(d)) + 1)


class ModelosEnergia(unittest.TestCase):
    def test_fisica_explica_energia(self):
        """Em toda agência, a fórmula física (média da frota da categoria) explica o kWh por devolução."""
        for ag in AGENCIAS:
            with self.subTest(ag=ag):
                a = E.avaliar_contratos(F.carregar(ag))
                self.assertGreater(a["metricas"].loc["física (frota da categoria)", "R2"], 0.8)
                imp = a["importancia_gbm_bruto"]
                self.assertIn(imp.index[0], ("km_devolucao", "rank"))  # o que manda é km e categoria


class NotaEstimada(unittest.TestCase):
    def test_convencao_do_kit(self):
        """Mesma convenção de kickoff.nota.pontuar: soma de peso × métrica (sinal no peso)."""
        cen = F.carregar(BASE)
        cat = {"pesos": {cen.agencia.nome: {"certo": 10, "upgrade": 6, "nao_atendido": -50, "demanda_contratada": -1,
                                            "energia_ponta_kwh": -0.1, "infraestrutura": -1}},
               "carregadores": [{"id": k, "custo": 100} for k in cen.carregadores],
               "entradas": [{"id": k, "custo": 1000} for k in cen.entradas]}
        m = {"certos": 200, "upgrades": 10, "nao_atendidos": 5, "energia_ponta_kwh": 50, "demanda_contratada_kw": 0}
        n = C.nota_estimada(cen, cat, {next(iter(cen.carregadores)): 2}, cen.agencia.entrada_existente, m)
        self.assertAlmostEqual(n, 10 * 200 + 6 * 10 - 50 * 5 - 0.1 * 50 - 200)


if __name__ == "__main__":
    unittest.main()
