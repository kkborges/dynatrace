import json
import unittest

from tests.helpers import TempWorkspaceTest, _response

from dtdash.client import DynatraceClient, extract_id, extract_version
from dtdash.config import TenantProfile
from dtdash.selftest import FAIL, OK, SKIP, WARN, SelfTest


def profile():
    return TenantProfile(
        name="t", environment_id="abc12345", platform_token="dt0s16.TOKEN"
    ).normalize()


class FakeTenant(object):
    """Tenant simulado com defeitos configuraveis."""

    def __init__(self, id_key="id", segment_id_key="uid", has_verify=True,
                 keeps_tile_segments=True, has_env_shares=True, dps=True,
                 missing_metrics=(), broken_blueprint=None, segment_write_error=False):
        self.id_key = id_key
        self.segment_id_key = segment_id_key
        self.has_verify = has_verify
        self.keeps_tile_segments = keeps_tile_segments
        self.has_env_shares = has_env_shares
        self.dps = dps
        self.missing_metrics = set(missing_metrics)
        self.broken_blueprint = broken_blueprint
        self.segment_write_error = segment_write_error
        self.documents = {}
        self.segments = {}
        self.calls = []
        self._counter = 0

    def __call__(self, method, url, headers=None, data=None, timeout=None, verify=True, **kw):
        method = method.upper()
        self.calls.append((method, url))
        body = {}
        if data and isinstance(data, bytes) and data[:1] in (b"{", b"["):
            try:
                body = json.loads(data.decode("utf-8"))
            except ValueError:
                body = {}

        if "query:verify" in url:
            if not self.has_verify:
                return _response(404, {}, url)
            query = body.get("query") or ""
            invalid = "filtre" in query or (
                self.broken_blueprint and self.broken_blueprint in query)
            return _response(200, {
                "valid": not invalid,
                "notifications": [] if not invalid else [
                    {"severity": "ERROR", "message": "sintaxe invalida"}],
            }, url)

        if "query:execute" in url:
            return _response(200, {"state": "SUCCEEDED",
                                   "result": {"records": self._records(body.get("query") or "")}},
                             url)

        if "filter-segments" in url:
            if method == "GET" and url.rstrip("/").endswith(":lean"):
                return _response(200, {"filterSegments": list(self.segments.values())}, url)
            if method == "POST":
                if self.segment_write_error:
                    return _response(403, {"error": {"message": "escopo ausente"}}, url)
                self._counter += 1
                uid = "seg-%d" % self._counter
                created = dict(body)
                created[self.segment_id_key] = uid
                created["version"] = 1
                self.segments[uid] = created
                return _response(201, created, url)
            uid = url.rstrip("/").split("/")[-1].split("?")[0]
            if method == "GET":
                if uid not in self.segments:
                    return _response(404, {}, url)
                return _response(200, self.segments[uid], url)
            if method == "DELETE":
                self.segments.pop(uid, None)
                return _response(204, b"", url)

        if "environment-shares" in url:
            if not self.has_env_shares:
                return _response(404, {}, url)
            return _response(201, {"id": "share-1"}, url)

        if "/documents" in url:
            if method == "POST":
                self._counter += 1
                document_id = "doc-%d" % self._counter
                content = _multipart_json(data)
                if not self.keeps_tile_segments:
                    for tile in (content.get("tiles") or {}).values():
                        tile.pop("segments", None)
                self.documents[document_id] = {"content": content, "version": 1}
                return _response(201, {self.id_key: document_id, "version": 1}, url)
            if method == "GET" and url.endswith("/content"):
                document_id = url.split("/documents/")[1].split("/")[0]
                if document_id not in self.documents:
                    return _response(404, {}, url)
                return _response(200, self.documents[document_id]["content"], url)
            if method == "GET" and "/documents/" in url:
                document_id = url.split("/documents/")[1].split("?")[0]
                return _response(200, {self.id_key: document_id, "version": 1}, url)
            if method == "GET":
                return _response(200, {"documents": [
                    {self.id_key: d, "name": "existente"} for d in self.documents]}, url)
            if method == "PATCH":
                return _response(200, {"id": "patched"}, url)
            if method == "DELETE":
                document_id = url.split("/documents/")[1].split("?")[0]
                self.documents.pop(document_id, None)
                return _response(204, b"", url)

        return _response(404, {"error": {"message": "rota nao simulada: %s" % url}}, url)

    def _records(self, query):
        if "dt.system.data_objects" in query:
            return [{"name": n} for n in ("logs", "spans", "events", "bizevents",
                                          "user.events", "security.events",
                                          "dt.davis.problems", "dt.system.events")]
        if "BILLING_USAGE_EVENT" in query:
            return [{"event.type": "Log Management & Analytics - Ingest & Process",
                     "events": 42}] if self.dps else []
        if query.strip().startswith("metrics"):
            import re

            keys = re.findall(r'"([^"]+)"', query)
            return [{"metric.key": k} for k in keys if k not in self.missing_metrics]
        if query.strip().startswith("data record"):
            return [{"dtdash": "selftest"}]
        return []


def _multipart_json(data):
    text = (data or b"").decode("utf-8", "replace")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return {}


class SelfTestReadOnlyTest(unittest.TestCase):
    def run_selftest(self, tenant=None, **kwargs):
        tenant = tenant or FakeTenant()
        client = DynatraceClient(profile(), transport=tenant)
        report = SelfTest(client).run(**kwargs)
        return report, tenant

    def status_of(self, report, check_id):
        for check in report.checks:
            if check.check_id == check_id:
                return check
        raise AssertionError("verificacao '%s' nao encontrada" % check_id)

    def test_tenant_saudavel_passa(self):
        report, _ = self.run_selftest()
        self.assertTrue(report.ok, [c.to_dict() for c in report.checks if c.status == FAIL])
        for check_id in ("config", "auth", "documents.read", "segments.read",
                         "grail.execute", "grail.verify", "grail.dataobjects"):
            self.assertEqual(self.status_of(report, check_id).status, OK, check_id)

    def test_modo_leitura_nao_escreve_no_tenant(self):
        report, tenant = self.run_selftest()
        escritas = [c for c in tenant.calls
                    if c[0] in ("POST", "PATCH", "DELETE") and "query:" not in c[1]]
        self.assertEqual(escritas, [])
        self.assertEqual(self.status_of(report, "documents.write").status, SKIP)

    def test_todas_as_dql_do_catalogo_sao_validas(self):
        report, _ = self.run_selftest()
        check = self.status_of(report, "dql.blueprints")
        self.assertEqual(check.status, OK, check.detail)
        self.assertGreater(check.data["total"], 50)

    def test_blueprint_quebrado_e_reportado(self):
        tenant = FakeTenant(broken_blueprint="dt.kubernetes.container.oom_kills")
        report, _ = self.run_selftest(tenant)
        check = self.status_of(report, "dql.blueprints")
        self.assertEqual(check.status, FAIL)
        self.assertIn("k8s.oom", [i["blueprint"] for i in check.data["invalid"]])

    def test_verify_ausente_vira_aviso_e_pula_as_queries(self):
        report, _ = self.run_selftest(FakeTenant(has_verify=False))
        self.assertEqual(self.status_of(report, "grail.verify").status, WARN)
        self.assertEqual(self.status_of(report, "dql.blueprints").status, SKIP)
        self.assertTrue(report.ok)

    def test_metrica_ausente_vira_aviso_com_blueprints_afetados(self):
        tenant = FakeTenant(missing_metrics={"dt.kubernetes.container.oom_kills"})
        report, _ = self.run_selftest(tenant)
        check = self.status_of(report, "metrics.catalog")
        self.assertEqual(check.status, WARN)
        self.assertIn("k8s.oom", check.data["affectedBlueprints"])

    def test_ausencia_de_dps_nao_e_falha(self):
        report, _ = self.run_selftest(FakeTenant(dps=False))
        check = self.status_of(report, "grail.dps")
        self.assertEqual(check.status, WARN)
        self.assertIn("entitlement", check.detail)
        self.assertTrue(report.ok)

    def test_falha_de_autenticacao_interrompe_com_seguranca(self):
        def transport(method, url, **kwargs):
            return _response(401, {"error": {"message": "token invalido"}}, url)

        perfil = profile()
        perfil.auth_method = "oauth"
        perfil.oauth_client_id = "cid"
        perfil.oauth_client_secret = "secret"
        client = DynatraceClient(perfil, transport=transport)
        report = SelfTest(client).run()
        self.assertFalse(report.ok)
        self.assertEqual(self.status_of(report, "auth").status, FAIL)
        self.assertEqual(self.status_of(report, "abortado").status, SKIP)


class SelfTestWriteTest(SelfTestReadOnlyTest):
    def test_ciclo_de_escrita_cria_e_remove_tudo(self):
        report, tenant = self.run_selftest(write=True, queries=False, metrics=False)
        self.assertTrue(report.ok, [c.to_dict() for c in report.checks if c.status == FAIL])
        self.assertEqual(self.status_of(report, "segments.write").status, OK)
        self.assertEqual(self.status_of(report, "documents.write").status, OK)
        self.assertEqual(self.status_of(report, "tile.segments").status, OK)
        self.assertEqual(self.status_of(report, "documents.share").status, OK)
        self.assertEqual(self.status_of(report, "cleanup").status, OK)
        self.assertEqual(tenant.documents, {})
        self.assertEqual(tenant.segments, {})

    def test_identificador_alternativo_e_reconhecido(self):
        tenant = FakeTenant(id_key="documentId", segment_id_key="id")
        report, _ = self.run_selftest(tenant, write=True, queries=False, metrics=False)
        self.assertEqual(self.status_of(report, "documents.write").status, OK)
        self.assertEqual(self.status_of(report, "documents.write").data["idKey"], "documentId")
        self.assertEqual(self.status_of(report, "segments.write").status, OK)

    def test_segments_perdidos_no_round_trip_viram_aviso(self):
        tenant = FakeTenant(keeps_tile_segments=False)
        report, _ = self.run_selftest(tenant, write=True, queries=False, metrics=False)
        check = self.status_of(report, "tile.segments")
        self.assertEqual(check.status, WARN)
        self.assertIn("--segment-mode dql", check.detail)
        self.assertTrue(report.ok)

    def test_share_cai_para_patch_quando_nao_ha_environment_shares(self):
        tenant = FakeTenant(has_env_shares=False)
        report, _ = self.run_selftest(tenant, write=True, queries=False, metrics=False)
        check = self.status_of(report, "documents.share")
        self.assertEqual(check.status, OK)
        self.assertEqual(check.data["result"]["method"], "patch-isPrivate")

    def test_limpeza_roda_mesmo_com_falha_no_meio(self):
        tenant = FakeTenant(segment_write_error=True)
        report, _ = self.run_selftest(tenant, write=True, queries=False, metrics=False)
        self.assertEqual(self.status_of(report, "segments.write").status, FAIL)
        self.assertEqual(self.status_of(report, "cleanup").status, OK)
        self.assertEqual(tenant.documents, {}, "o dashboard temporario deve ser removido")

    def test_no_cleanup_mantem_os_objetos(self):
        report, tenant = self.run_selftest(write=True, cleanup=False, queries=False,
                                           metrics=False)
        self.assertEqual(len(tenant.documents), 2)
        self.assertEqual(len(tenant.segments), 1)


class ReportTest(unittest.TestCase):
    def test_texto_e_json_do_relatorio(self):
        client = DynatraceClient(profile(), transport=FakeTenant())
        report = SelfTest(client).run()
        text = report.to_text()
        self.assertIn("dtdash selftest", text)
        self.assertIn("[ ok ]", text)
        payload = report.to_dict()
        self.assertIn("counts", payload)
        self.assertEqual(len(payload["checks"]), len(report.checks))


class ExtractorTest(unittest.TestCase):
    def test_variacoes_de_identificador(self):
        self.assertEqual(extract_id({"id": "a"}), "a")
        self.assertEqual(extract_id({"uid": "b"}), "b")
        self.assertEqual(extract_id({"documentId": "c"}), "c")
        self.assertEqual(extract_id({"document": {"uid": "d"}}), "d")
        self.assertEqual(extract_id({"nada": 1}), "")

    def test_variacoes_de_versao(self):
        self.assertEqual(extract_version({"version": 2}), 2)
        self.assertEqual(extract_version({"document": {"optimisticLockingVersion": 5}}), 5)
        self.assertIsNone(extract_version({}))


class ServiceSelfTestTest(TempWorkspaceTest):
    def test_service_salva_o_relatorio(self):
        from dtdash.service import DashboardService

        service = DashboardService(self.workspace, self.config)
        perfil = self.add_tenant()
        service._clients[perfil.name] = DynatraceClient(perfil, transport=FakeTenant())
        report, path = service.selftest(tenant=perfil.name, queries=False, metrics=False)
        self.assertTrue(report.ok)
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["tenant"], perfil.name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
