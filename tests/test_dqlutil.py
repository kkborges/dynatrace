from tests.helpers import TempWorkspaceTest  # noqa: F401  (garante o sys.path)

import unittest

from dtdash import dqlutil


class InjectFiltersTest(unittest.TestCase):
    def test_timeseries_recebe_parametro_filter(self):
        query = "timeseries cpu = avg(dt.host.cpu.usage), by:{dt.smartscape.host}\n| fieldsAdd x=1"
        out = dqlutil.inject_filters(query, ['k8s.namespace.name == "pag"'])
        self.assertIn('by:{dt.smartscape.host}, filter: { k8s.namespace.name == "pag" }', out)
        self.assertTrue(out.splitlines()[1].startswith("| fieldsAdd"))

    def test_timeseries_multilinha(self):
        query = "timeseries {\n  a = avg(m1),\n  b = avg(m2)\n}, by:{x}\n| fields a"
        out = dqlutil.inject_filters(query, ["e1", "e2"])
        self.assertIn("}, by:{x}, filter: { e1 and e2 }", out)

    def test_timeseries_combina_com_filtro_existente(self):
        query = "timeseries a = avg(m), by:{x}, filter: { y == 1 }"
        out = dqlutil.inject_filters(query, ["z == 2"])
        self.assertIn("filter: {y == 1 and z == 2}", out)

    def test_fetch_recebe_etapa_de_filtro_apos_a_origem(self):
        query = "fetch logs\n| filter status == \"ERROR\"\n| summarize c = count()"
        out = dqlutil.inject_filters(query, ["host.name == $Host"])
        lines = out.splitlines()
        self.assertEqual(lines[0], "fetch logs")
        self.assertEqual(lines[1], "| filter host.name == $Host")

    def test_sem_expressoes_mantem_query(self):
        query = "fetch logs"
        self.assertEqual(dqlutil.inject_filters(query, []), query)

    def test_deteccao_de_origem(self):
        self.assertEqual(dqlutil.detect_source_kind("timeseries a = avg(m)"), "timeseries")
        self.assertEqual(dqlutil.detect_source_kind("fetch logs"), "fetch")
        self.assertEqual(dqlutil.detect_source_kind('smartscapeNodes "HOST"'), "smartscape")


class LintTest(unittest.TestCase):
    def test_detecta_loglevel_errado(self):
        self.assertTrue(any("loglevel" in w for w in dqlutil.lint('fetch logs | filter log.level == "ERROR"')))

    def test_detecta_sort_sem_crase(self):
        self.assertTrue(any("crase" in w for w in dqlutil.lint("fetch logs | sort count() desc")))

    def test_detecta_array_literal_incorreto(self):
        warnings = dqlutil.lint('fetch logs | filter status in ["A","B"]')
        self.assertTrue(any("colchetes" in w for w in warnings))

    def test_query_valida_nao_gera_avisos(self):
        query = 'fetch logs\n| filter in(status, {"ERROR"})\n| summarize c = count(), by:{host.name}'
        self.assertEqual(dqlutil.lint(query), [])


class HelpersTest(unittest.TestCase):
    def test_quote_escapa_aspas(self):
        self.assertEqual(dqlutil.quote('a"b'), '"a\\"b"')

    def test_in_values(self):
        self.assertEqual(dqlutil.in_values("f", ["a"]), 'f == "a"')
        self.assertEqual(dqlutil.in_values("f", ["a", "b"]), 'in(f, {"a", "b"})')

    def test_variable_filter(self):
        self.assertEqual(dqlutil.variable_filter("f", "V"), "f == $V")
        self.assertEqual(dqlutil.variable_filter("f", "V", True), "in(f, array($V))")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
