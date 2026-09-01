import json
import os
import unittest

from tests.helpers import TempWorkspaceTest

from dtdash.config import Config, TenantProfile, Workspace
from dtdash.errors import ConfigError


class TenantProfileTest(unittest.TestCase):
    def test_normaliza_urls_a_partir_do_environment_id(self):
        profile = TenantProfile(name="p", environment_id="abc12345").normalize()
        self.assertEqual(profile.platform_url, "https://abc12345.apps.dynatrace.com")
        self.assertEqual(profile.environment_url, "https://abc12345.live.dynatrace.com")

    def test_extrai_environment_id_da_url(self):
        profile = TenantProfile(name="p", platform_url="xyz98765.apps.dynatrace.com").normalize()
        self.assertEqual(profile.environment_id, "xyz98765")
        self.assertTrue(profile.platform_url.startswith("https://"))

    def test_credenciais_vem_do_ambiente(self):
        os.environ["DT_TEST_TOKEN_XYZ"] = "dt0s16.ABC"
        profile = TenantProfile(name="p", environment_id="abc12345",
                                platform_token_env="DT_TEST_TOKEN_XYZ").normalize()
        self.assertTrue(profile.has_credentials())
        self.assertEqual(profile.resolve_platform_token(), "dt0s16.ABC")
        del os.environ["DT_TEST_TOKEN_XYZ"]

    def test_validate_exige_credenciais(self):
        profile = TenantProfile(name="p", environment_id="abc12345",
                                platform_token_env="NAO_EXISTE_XYZ").normalize()
        self.assertRaises(ConfigError, profile.validate)

    def test_segredos_sao_ocultados(self):
        profile = TenantProfile(name="p", platform_token="dt0s16.SECRETO").normalize()
        self.assertEqual(profile.to_dict()["platform_token"], "***")
        self.assertEqual(profile.to_dict(redact=False)["platform_token"], "dt0s16.SECRETO")


class ConfigTest(TempWorkspaceTest):
    def test_salva_e_recarrega_tenants(self):
        config = Config(self.workspace, {"tenants": {}, "settings": {}})
        config.put_tenant(TenantProfile(name="a", environment_id="abc12345"))
        config.put_tenant(TenantProfile(name="b", environment_id="def45678"))
        path = config.save()
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as handle:
            self.assertIn("a", json.load(handle)["tenants"])
        recarregado = Config.load(self.workspace)
        self.assertEqual(recarregado.tenant_names(), ["a", "b"])
        self.assertEqual(recarregado.get_tenant().name, "a")

    def test_tenant_desconhecido(self):
        config = Config(self.workspace, {"tenants": {}, "settings": {}})
        self.assertRaises(ConfigError, config.get_tenant, "inexistente")

    def test_define_tenant_padrao(self):
        config = Config(self.workspace, {"tenants": {}, "settings": {}})
        config.put_tenant(TenantProfile(name="a", environment_id="abc12345"))
        config.put_tenant(TenantProfile(name="b", environment_id="def45678"))
        config.set_default_tenant("b")
        self.assertEqual(config.get_tenant().name, "b")

    def test_workspace_cria_estrutura(self):
        workspace = Workspace(self.tmp).ensure()
        for path in (workspace.library_dir, workspace.clients_dir, workspace.proposals_dir,
                     workspace.knowledge_seed_dir, workspace.examples_dir):
            self.assertTrue(os.path.isdir(path), path)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
