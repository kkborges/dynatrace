import json
import unittest

from tests.helpers import TempWorkspaceTest, _response

from dtdash.capabilities import (
    STATUS_DENIED,
    STATUS_EMPTY,
    STATUS_OK,
    TenantCapabilities,
    probe_tables,
)
from dtdash.client import DynatraceClient
from dtdash.config import TenantProfile
from dtdash.errors import ApiError
from dtdash.knowledge.store import KnowledgeStore
from dtdash.metrics import ALIAS, MISSING, OK, UNKNOWN, MetricCatalogView, rewrite_query
from dtdash.planner import Planner
from dtdash.validator import validate_spec
from dtdash.builder import build_dashboard


def profile():
    return TenantProfile(name="t", environment_id="abc12345",
                         platform_token="dt0s16.T").normalize()


class FakeGrail(object):
    """Tenant Grail simulado: indice de metricas e tabelas negadas configuraveis."""

    def __init__(self, metric_index=None, denied_tables=(), empty_tables=(),
                 metrics_index_empty=False):
        self.metric_index = list(metric_index or [])
        self.denied_tables = set(denied_tables)
        self.empty_tables = set(empty_tables)
        self.metrics_index_empty = metrics_index_empty
        self.queries = []

    def __call__(self, method, url, headers=None, data=None, **kwargs):
        if "query:execute" not in url:
            return _response(200, {}, url)
        body = json.loads(data.decode("utf-8"))
        query = body.get("query") or ""
        self.queries.append(query)
        table = self._table_of(query)
        if table in self.denied_tables:
            return _response(403, {"error": {
                "message": "NOT_AUTHORIZED_FOR_TABLE",
                "details": {"exception": "missing permission for table %s" % table}}}, url)
        if query.strip().startswith("metrics"):
            if self.metrics_index_empty:
                return _response(200, {"state": "SUCCEEDED", "result": {"records": []}}, url)
            return _response(200, {"state": "SUCCEEDED", "result": {
                "records": [{"metric.key": k} for k in self.metric_index]}}, url)
        if table in self.empty_tables:
            return _response(200, {"state": "SUCCEEDED", "result": {"records": []}}, url)
        if "dt.system.data_objects" in query:
            return _response(200, {"state": "SUCCEEDED", "result": {"records": [
                {"name": n} for n in ("logs", "spans", "events", "dt.davis.problems",
                                      "dt.system.events", "bizevents", "user.events",
                                      "security.events")]}}, url)
        return _response(200, {"state": "SUCCEEDED",
                               "result": {"records": [{"timestamp": "2026-01-01"}]}}, url)

    def _table_of(self, query):
        stripped = query.strip()
        if stripped.startswith("metrics") or stripped.startswith("timeseries"):
            return "metrics"
        if stripped.startswith("smartscapeNodes"):
            return "smartscape"
        if stripped.startswith("fetch "):
            return stripped.split()[1].rstrip(",")
        return ""

    def client(self):
        return DynatraceClient(profile(), transport=self)


GRAIL_KEYS = ["dt.host.cpu.usage", "dt.host.memory.usage", "dt.host.disk.used.percent",
              "dt.service.request.count", "dt.service.request.failure_count",
              "dt.service.request.response_time"]
CLASSIC_KEYS = ["builtin:host.cpu.usage", "builtin:host.mem.usage",
                "builtin:host.disk.usedPct", "builtin:service.requestCount.total",
                "builtin:service.errors.total.count", "builtin:service.response.time"]


class ErrorCodeTest(unittest.TestCase):
    def test_detecta_nao_autorizado(self):
        tenant = FakeGrail(denied_tables={"metrics"})
        with self.assertRaises(ApiError) as ctx:
            tenant.client().execute_query("timeseries a = avg(dt.host.cpu.usage)")
        self.assertEqual(ctx.exception.code, "NOT_AUTHORIZED_FOR_TABLE")
        self.assertTrue(ctx.exception.unauthorized)

    def test_erro_comum_nao_e_de_permissao(self):
        error = ApiError("x", status=400, payload={"error": {"message": "sintaxe"}})
        self.assertFalse(error.unauthorized)


class TableProbeTest(unittest.TestCase):
    def test_classifica_tabelas(self):
        tenant = FakeGrail(metric_index=GRAIL_KEYS, denied_tables={"metrics", "smartscape"},
                           empty_tables={"bizevents"})
        tables = probe_tables(tenant.client())
        self.assertEqual(tables["metrics"]["status"], STATUS_DENIED)
        self.assertEqual(tables["metrics"]["permission"], "storage:metrics:read")
        self.assertEqual(tables["smartscape"]["status"], STATUS_DENIED)
        self.assertEqual(tables["logs"]["status"], STATUS_OK)
        self.assertEqual(tables["bizevents"]["status"], STATUS_EMPTY)

    def test_capacidades_resumem_permissoes_faltando(self):
        tenant = FakeGrail(denied_tables={"metrics", "smartscape"})
        caps = TenantCapabilities.probe(tenant.client())
        self.assertEqual(caps.denied_tables(), ["metrics", "smartscape"])
        self.assertIn("storage:metrics:read", caps.missing_permissions())
        self.assertIs(caps.table_readable("metrics"), False)
        self.assertIs(caps.table_readable("logs"), True)
        self.assertIsNone(TenantCapabilities.offline().table_readable("logs"))


class MetricResolutionTest(unittest.TestCase):
    def view(self, tenant, caps=None):
        return MetricCatalogView.load(tenant.client(), caps)

    def test_tenant_grail_resolve_direto(self):
        view = self.view(FakeGrail(metric_index=GRAIL_KEYS))
        resolutions = view.resolve_all(GRAIL_KEYS)
        self.assertTrue(all(r.status == OK for r in resolutions.values()))

    def test_tenant_classico_usa_alias_e_reescreve_a_query(self):
        view = self.view(FakeGrail(metric_index=CLASSIC_KEYS))
        resolutions = view.resolve_all(GRAIL_KEYS)
        self.assertTrue(all(r.status == ALIAS for r in resolutions.values()))
        query = rewrite_query(
            "timeseries cpu = avg(dt.host.cpu.usage), by:{dt.smartscape.host}", resolutions)
        self.assertIn("`builtin:host.cpu.usage`", query)
        self.assertNotIn("avg(dt.host.cpu.usage)", query)

    def test_metrica_inexistente_e_marcada_como_missing_com_sugestao(self):
        view = self.view(FakeGrail(metric_index=["dt.host.cpu.usage.custom"]))
        resolution = view.resolve("dt.host.cpu.usage")
        self.assertEqual(resolution.status, MISSING)
        self.assertIn("dt.host.cpu.usage.custom", resolution.suggestions)

    def test_sem_permissao_no_indice_e_inconclusivo(self):
        tenant = FakeGrail(denied_tables={"metrics"})
        view = self.view(tenant)
        self.assertIs(view.available, False)
        self.assertIn("storage:metrics:read", view.reason)
        self.assertEqual(view.resolve("dt.host.cpu.usage").status, UNKNOWN)

    def test_indice_vazio_e_inconclusivo_e_nao_missing(self):
        view = self.view(FakeGrail(metrics_index_empty=True))
        self.assertIs(view.available, False)
        self.assertIn("vazio", view.reason)
        self.assertEqual(view.resolve("dt.host.cpu.usage").status, UNKNOWN)

    def test_offline_e_inconclusivo(self):
        view = MetricCatalogView.load(None)
        self.assertIsNone(view.available)
        self.assertEqual(view.resolve("dt.host.cpu.usage").status, UNKNOWN)

    def test_backticks_apenas_quando_necessario(self):
        from dtdash.metrics import needs_backticks

        self.assertTrue(needs_backticks("builtin:host.cpu.usage"))
        self.assertFalse(needs_backticks("dt.host.cpu.usage"))


class PlannerMetricPolicyTest(TempWorkspaceTest):
    def planner(self, tenant, caps=None):
        caps = caps or TenantCapabilities.probe(tenant.client())
        return Planner(knowledge=KnowledgeStore(self.workspace).build(),
                       client=tenant.client(), capabilities=caps)

    def test_tenant_classico_gera_dashboard_com_chaves_classicas(self):
        tenant = FakeGrail(metric_index=CLASSIC_KEYS)
        spec = self.planner(tenant).plan("cpu e memoria dos hosts e taxa de erro dos servicos")
        queries = " ".join(t.query for t in spec.data_tiles())
        self.assertIn("`builtin:host.cpu.usage`", queries)
        self.assertNotIn("avg(dt.host.cpu.usage)", queries)
        self.assertTrue(any("classica" in w for w in spec.warnings))
        self.assertTrue(validate_spec(spec, build_dashboard(spec)).ok)

    def test_metrica_ausente_remove_o_tile_por_padrao(self):
        tenant = FakeGrail(metric_index=["dt.service.request.count",
                                         "dt.service.request.failure_count",
                                         "dt.service.request.response_time"])
        spec = self.planner(tenant).plan("cpu dos hosts e taxa de erro dos servicos")
        titulos = [t.title for t in spec.data_tiles()]
        self.assertNotIn("CPU por host (media)", titulos)
        self.assertTrue(spec.dropped_tiles)
        self.assertTrue(any("removidos" in w for w in spec.warnings))

    def test_on_missing_keep_mantem_o_tile_sinalizado(self):
        tenant = FakeGrail(metric_index=["dt.service.request.count"])
        spec = self.planner(tenant).plan("cpu dos hosts", on_missing="keep")
        indisponiveis = [t for t in spec.tiles if t.availability == "missing"]
        self.assertTrue(indisponiveis)
        self.assertFalse(spec.dropped_tiles)
        report = validate_spec(spec, build_dashboard(spec))
        self.assertTrue(any(f.rule == "metrics" and "inexistente" in f.message
                            for f in report.findings))

    def test_sem_permissao_mantem_tiles_e_avisa_a_permissao(self):
        tenant = FakeGrail(denied_tables={"metrics"})
        spec = self.planner(tenant).plan("cpu e memoria dos hosts")
        self.assertFalse(spec.dropped_tiles)
        self.assertTrue(any("storage:metrics:read" in w for w in spec.warnings))
        self.assertTrue(all(t.availability in ("ok", "unverified") for t in spec.tiles))
        report = validate_spec(spec, build_dashboard(spec))
        self.assertTrue(any(f.rule == "permissions" for f in report.findings))

    def test_nenhuma_secao_fica_sem_tile_apos_as_remocoes(self):
        tenant = FakeGrail(metric_index=["dt.service.request.count",
                                         "dt.service.request.failure_count",
                                         "dt.service.request.response_time"])
        spec = self.planner(tenant).plan(
            "cpu, memoria e disco dos hosts, pods do kubernetes e taxa de erro dos servicos")
        self.assertTrue(spec.dropped_tiles)
        secoes = []
        for tile in spec.tiles:
            if tile.kind == "markdown" and (tile.markdown or "").startswith("## "):
                secoes.append([tile.markdown.strip(), 0])
            elif tile.kind == "data" and secoes:
                secoes[-1][1] += 1
        vazias = [nome for nome, total in secoes if total == 0]
        self.assertEqual(vazias, [], "secoes sem tiles: %s" % vazias)
        self.assertTrue(validate_spec(spec, build_dashboard(spec)).ok)

    def test_dashboard_permanece_valido_apos_remocoes(self):
        tenant = FakeGrail(metric_index=CLASSIC_KEYS[:1])
        spec = self.planner(tenant).plan("saude completa: hosts, servicos, kubernetes e logs")
        document = build_dashboard(spec)
        report = validate_spec(spec, document)
        self.assertTrue(report.ok, [f.message for f in report.errors])
        self.assertEqual(set(document["content"]["tiles"]),
                         set(document["content"]["layouts"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
