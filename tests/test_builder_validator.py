import unittest

from tests.helpers import TempWorkspaceTest

from dtdash.builder import build_dashboard, dashboard_to_spec, pack_layout
from dtdash.knowledge.store import KnowledgeStore
from dtdash.planner import Planner
from dtdash.spec import DashboardSpec, TileSpec, VariableSpec
from dtdash.validator import validate_document, validate_spec
from dtdash.version import DASHBOARD_CONTENT_VERSION


def tile(tile_id, **kwargs):
    return TileSpec(tile_id=tile_id, **kwargs)


class LayoutTest(unittest.TestCase):
    def test_tiles_nao_se_sobrepoem(self):
        tiles = [tile(str(i), width=12, height=6) for i in range(1, 7)]
        layouts = pack_layout(tiles)
        boxes = list(layouts.values())
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                overlap = (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                           and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])
                self.assertFalse(overlap, "sobreposicao entre %s e %s" % (a, b))

    def test_markdown_ocupa_linha_inteira(self):
        tiles = [tile("1", width=12), tile("2", kind="markdown", width=24), tile("3", width=12)]
        layouts = pack_layout(tiles)
        self.assertEqual(layouts["2"]["x"], 0)
        self.assertEqual(layouts["2"]["w"], 24)
        self.assertEqual(layouts["3"]["x"], 0)
        self.assertGreater(layouts["3"]["y"], layouts["2"]["y"])

    def test_largura_maior_que_a_grade_e_limitada(self):
        layouts = pack_layout([tile("1", width=40)])
        self.assertEqual(layouts["1"]["w"], 24)


class BuildTest(unittest.TestCase):
    def test_documento_tem_estrutura_da_plataforma(self):
        spec = DashboardSpec(
            name="Teste",
            tiles=[tile("1", kind="markdown", markdown="# oi", width=24, height=2),
                   tile("2", title="T", query="fetch logs", visualization="table")],
        )
        document = build_dashboard(spec)
        self.assertEqual(document["type"], "dashboard")
        self.assertEqual(document["content"]["version"], DASHBOARD_CONTENT_VERSION)
        self.assertEqual(set(document["content"]["tiles"]), set(document["content"]["layouts"]))
        self.assertEqual(document["content"]["settings"]["gridLayout"]["columnsCount"], 24)

    def test_variavel_multipla_recebe_token_de_selecionar_tudo(self):
        spec = DashboardSpec(
            name="T",
            variables=[VariableSpec(key="V", input="fetch logs | fields x", multiple=True,
                                    default_value="3420b2ac-f1cf-4b24-b62d-61ba1ba8ed05*")],
            tiles=[tile("1", title="a", query="fetch logs | filter in(x, array($V))")],
        )
        variable = build_dashboard(spec)["content"]["variables"][0]
        self.assertTrue(variable["multiple"])
        self.assertEqual(variable["defaultValue"], "3420b2ac-f1cf-4b24-b62d-61ba1ba8ed05*")

    def test_segments_resolvidos_para_uid(self):
        spec = DashboardSpec(
            name="T", tiles=[tile("1", title="a", query="fetch logs", segments=["k1"])]
        )
        document = build_dashboard(spec, segment_uids={"k1": "uid-123"})
        self.assertEqual(document["content"]["tiles"]["1"]["segments"], ["uid-123"])

    def test_segment_sem_uid_e_omitido(self):
        spec = DashboardSpec(
            name="T", tiles=[tile("1", title="a", query="fetch logs", segments=["k1"])]
        )
        document = build_dashboard(spec, segment_uids={})
        self.assertNotIn("segments", document["content"]["tiles"]["1"])

    def test_roundtrip_documento_para_spec(self):
        spec = DashboardSpec(
            name="Origem",
            tiles=[tile("1", kind="markdown", markdown="# t", width=24, height=2),
                   tile("2", title="Erros", query="fetch logs", visualization="table")],
        )
        document = build_dashboard(spec)
        restored = dashboard_to_spec(document)
        self.assertEqual(restored.name, "Origem")
        self.assertEqual(len(restored.tiles), 2)
        self.assertEqual(restored.tiles[1].title, "Erros")


class ValidateTest(unittest.TestCase):
    def base_document(self):
        return {
            "name": "T", "type": "dashboard",
            "content": {
                "version": DASHBOARD_CONTENT_VERSION, "variables": [],
                "tiles": {"1": {"type": "data", "title": "a", "query": "fetch logs",
                                "visualization": "table"}},
                "layouts": {"1": {"x": 0, "y": 0, "w": 24, "h": 6}},
            },
        }

    def test_documento_valido(self):
        self.assertTrue(validate_document(self.base_document()).ok)

    def test_erro_quando_falta_layout(self):
        document = self.base_document()
        document["content"]["layouts"] = {}
        report = validate_document(document)
        self.assertFalse(report.ok)
        self.assertTrue(any("layout" in f.message for f in report.errors))

    def test_erro_quando_tiles_se_sobrepoem(self):
        document = self.base_document()
        document["content"]["tiles"]["2"] = dict(document["content"]["tiles"]["1"])
        document["content"]["layouts"]["2"] = {"x": 0, "y": 0, "w": 12, "h": 4}
        report = validate_document(document)
        self.assertTrue(any("sobrepostos" in f.message for f in report.errors))

    def test_erro_quando_tile_estoura_a_grade(self):
        document = self.base_document()
        document["content"]["layouts"]["1"] = {"x": 20, "y": 0, "w": 12, "h": 4}
        self.assertTrue(any("colunas" in f.message for f in validate_document(document).errors))

    def test_erro_quando_variavel_nao_declarada(self):
        document = self.base_document()
        document["content"]["tiles"]["1"]["query"] = "fetch logs | filter x == $Faltante"
        self.assertTrue(any("$Faltante" in f.message for f in validate_document(document).errors))

    def test_aviso_para_variavel_nao_usada(self):
        document = self.base_document()
        document["content"]["variables"] = [
            {"key": "Sobrando", "type": "query", "input": "fetch logs | fields x"}
        ]
        report = validate_document(document)
        self.assertTrue(any("nao usada" in f.message for f in report.warnings))

    def test_erro_de_visualizacao_temporal_sem_eixo_de_tempo(self):
        document = self.base_document()
        document["content"]["tiles"]["1"].update(
            visualization="lineChart", query="fetch logs | summarize c = count(), by:{host.name}"
        )
        self.assertTrue(any("temporal" in f.message for f in validate_document(document).errors))

    def test_erro_de_barchart_categorico(self):
        document = self.base_document()
        document["content"]["tiles"]["1"].update(
            visualization="barChart", query="fetch logs | summarize c = count(), by:{host.name}"
        )
        self.assertTrue(
            any("categoricalBarChart" in f.message for f in validate_document(document).errors)
        )

    def test_info_para_periodo_fixo_na_query(self):
        document = self.base_document()
        document["content"]["tiles"]["1"]["query"] = "fetch logs, from:-24h"
        findings = [f for f in validate_document(document).findings if f.rule == "timeframe"]
        self.assertTrue(findings)


class ValidateGeneratedTest(TempWorkspaceTest):
    def test_dashboards_gerados_passam_na_validacao(self):
        knowledge = KnowledgeStore(self.workspace).build()
        planner = Planner(knowledge=knowledge)
        pedidos = [
            "saude dos servicos em producao com taxa de erro e latencia p90",
            "kubernetes: pods reiniciando, cpu por namespace e erros de log",
            "resumo executivo de problemas ativos e usuarios impactados",
            "experiencia do usuario: sessoes, erros de frontend e web vitals",
            "consumo DPS por capacidade e custo de query no grail",
            "vulnerabilidades de seguranca abertas por risco",
            "eventos de negocio: volume de pedidos e conversao",
            "banco de dados: consultas lentas por servico",
        ]
        for pedido in pedidos:
            spec = planner.plan(pedido)
            document = build_dashboard(spec)
            report = validate_spec(spec, document)
            self.assertTrue(
                report.ok,
                "pedido '%s' gerou erros: %s"
                % (pedido, [f.message for f in report.errors]),
            )
            self.assertTrue(spec.data_tiles(), pedido)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
