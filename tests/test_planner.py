import unittest

from tests.helpers import TempWorkspaceTest

from dtdash.capabilities import TenantCapabilities
from dtdash.knowledge.store import KnowledgeStore
from dtdash.planner import Planner


class AnalysisTest(TempWorkspaceTest):
    def setUp(self):
        super().setUp()
        self.planner = Planner(knowledge=KnowledgeStore(self.workspace).build())

    def test_detecta_dominios_em_portugues(self):
        analysis = self.planner.analyze(
            "acompanhar pods reiniciando no cluster kubernetes e erros de log"
        )
        self.assertIn("kubernetes", analysis.domains)
        self.assertIn("logs", analysis.domains)

    def test_detecta_audiencia_executiva(self):
        analysis = self.planner.analyze("resumo gerencial para a diretoria sobre disponibilidade")
        self.assertEqual(analysis.audience, "exec")

    def test_detecta_audiencia_finops(self):
        analysis = self.planner.analyze("relatorio de chargeback e consumo DPS por centro de custo")
        self.assertEqual(analysis.audience, "finops")

    def test_extrai_namespace_e_ambiente(self):
        analysis = self.planner.analyze("erros no namespace pagamentos em producao")
        self.assertEqual(analysis.filters.get("namespace"), "pagamentos")
        self.assertEqual(analysis.filters.get("environment"), "producao")

    def test_extrai_janela_de_tempo(self):
        analysis = self.planner.analyze("erros das ultimas 24 horas")
        self.assertEqual(analysis.timeframe, "now()-24h")

    def test_dimensoes_sem_valor_viram_variaveis(self):
        analysis = self.planner.analyze("quero ver a latencia por servico")
        self.assertIn("service", analysis.dimensions)

    def test_requisitos_sao_separados(self):
        analysis = self.planner.analyze(
            "- taxa de erro por servico\n- latencia p90 dos endpoints\n- problemas ativos do davis"
        )
        self.assertEqual(len(analysis.requirements), 3)


class PlanTest(TempWorkspaceTest):
    def setUp(self):
        super().setUp()
        self.knowledge = KnowledgeStore(self.workspace).build()

    def plan(self, text, caps=None, **kwargs):
        planner = Planner(knowledge=self.knowledge, capabilities=caps)
        return planner.plan(text, **kwargs)

    def test_plano_gera_tiles_variaveis_e_segments(self):
        spec = self.plan(
            "dashboard de SRE para servicos em producao no namespace pagamentos: "
            "taxa de erro, latencia p90 e erros de log por servico"
        )
        self.assertTrue(spec.data_tiles())
        self.assertTrue(any(s.dimension == "namespace" for s in spec.segments))
        self.assertTrue(any(v.key == "Servico" for v in spec.variables))
        self.assertTrue(all(tile.tile_id for tile in spec.tiles))

    def test_toda_variavel_declarada_e_usada(self):
        spec = self.plan("latencia e erros por servico e por namespace no kubernetes")
        used = set()
        for tile in spec.tiles:
            for key in ("Servico", "Namespace", "Cluster", "Host", "Aplicacao"):
                if "$%s" % key in (tile.query or ""):
                    used.add(key)
        self.assertEqual({v.key for v in spec.variables} - used, set())

    def test_nao_injeta_filtro_de_servico_em_query_de_pods(self):
        spec = self.plan("pods do kubernetes por servico", segment_mode="dql")
        for tile in spec.tiles:
            if tile.blueprint == "k8s.pods_not_running":
                self.assertNotIn("$Servico", tile.query)

    def test_tiles_dps_ficam_de_fora_quando_nao_ha_consumo(self):
        caps = TenantCapabilities(online=True, dps=False, grail_queryable=True)
        spec = self.plan("saude dos servicos e latencia", caps=caps)
        self.assertFalse([t for t in spec.tiles if t.domain == "dps"])

    def test_tiles_dps_entram_quando_solicitado(self):
        caps = TenantCapabilities(online=True, dps=True, grail_queryable=True)
        spec = self.plan("analise de consumo DPS e custo de query no grail", caps=caps)
        self.assertTrue([t for t in spec.tiles if t.domain == "dps"])

    def test_dominio_indisponivel_no_tenant_e_ignorado(self):
        caps = TenantCapabilities(online=True, data_objects=["logs"], grail_queryable=True)
        spec = self.plan("vulnerabilidades de seguranca abertas por risco", caps=caps)
        self.assertFalse([t for t in spec.tiles if t.domain == "security"])

    def test_requisitos_recebem_cobertura(self):
        spec = self.plan("mostrar problemas ativos do davis e taxa de erro dos servicos")
        coverage = spec.coverage()
        self.assertTrue(any(coverage.get(r.req_id) for r in spec.requirements))

    def test_modo_de_segment_dql_embute_filtro(self):
        spec = self.plan(
            "erros de log no namespace pagamentos", segment_mode="dql"
        )
        queries = " ".join(t.query or "" for t in spec.tiles)
        self.assertIn('k8s.namespace.name == "pagamentos"', queries)

    def test_modo_de_segment_tile_nao_altera_query(self):
        spec = self.plan("erros de log no namespace pagamentos", segment_mode="tile")
        queries = " ".join(t.query or "" for t in spec.tiles)
        self.assertNotIn('k8s.namespace.name == "pagamentos"', queries)
        self.assertTrue(any(t.segments for t in spec.data_tiles()))

    def test_nome_do_dashboard_usa_dominios(self):
        spec = self.plan("resumo executivo de problemas e disponibilidade em producao")
        self.assertIn("Executivo", spec.name)
        self.assertIn("Producao", spec.name)

    def test_offline_marca_metricas_como_nao_verificadas(self):
        spec = self.plan("cpu e memoria dos hosts")
        self.assertTrue(any(t.unverified_metrics for t in spec.tiles))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class MinimumSizeTest(TempWorkspaceTest):
    def setUp(self):
        super().setUp()
        self.planner = Planner(knowledge=KnowledgeStore(self.workspace).build())

    def test_dashboard_pequeno_ganha_tiles_complementares(self):
        spec = self.planner.plan("consultas lentas no banco de dados")
        self.assertGreaterEqual(len(spec.data_tiles()), 6)

    def test_mensageria_cai_no_dominio_de_servicos(self):
        spec = self.planner.plan("monitorar filas kafka e mensageria")
        self.assertIn("services", spec.domains)
        self.assertTrue(any(t.blueprint == "messaging.throughput" for t in spec.tiles))


class SectionOrderTest(TempWorkspaceTest):
    def setUp(self):
        super().setUp()
        self.planner = Planner(knowledge=KnowledgeStore(self.workspace).build())

    def sections(self, spec):
        return [t.markdown.strip()[3:] for t in spec.tiles
                if t.kind == "markdown" and (t.markdown or "").startswith("## ")]

    def test_resumo_vem_primeiro_e_dps_por_ultimo(self):
        spec = self.planner.plan(
            "acompanhar custo DPS, erros de log e taxa de erro dos servicos")
        secoes = self.sections(spec)
        self.assertEqual(secoes[0], "Resumo executivo")
        self.assertEqual(secoes[-1], "Consumo da plataforma (DPS)")

    def test_secoes_seguem_a_relevancia_dos_dominios(self):
        spec = self.planner.plan(
            "pods do kubernetes reiniciando e, secundariamente, erros de log")
        secoes = self.sections(spec)
        self.assertIn("Kubernetes", secoes)
        self.assertLess(secoes.index("Kubernetes"), len(secoes))

    def test_consumo_de_cpu_nao_ativa_o_dominio_dps(self):
        spec = self.planner.plan(
            "hosts linux e windows em producao: consumo de cpu e consumo de memoria")
        self.assertNotIn("dps", spec.domains)

    def test_consumo_da_plataforma_ativa_o_dominio_dps(self):
        spec = self.planner.plan("acompanhar o consumo da plataforma e o custo de query")
        self.assertIn("dps", spec.domains)
