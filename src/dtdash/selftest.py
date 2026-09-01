"""Bateria de verificacao do dtdash contra um tenant real.

Roda as chamadas na mesma ordem em que o fluxo de publicacao as usa e reporta,
uma a uma, se a API respondeu como a documentacao descreve. Serve para descobrir
divergencias (nomes de campo, endpoints ausentes, escopos faltando) sem precisar
publicar um dashboard de verdade.

Por padrao e **somente leitura**. Com ``write=True`` o teste cria um segment e um
dashboard temporarios (prefixo ``dtdash-selftest``) e os remove ao final.
"""

import time
from dataclasses import dataclass, field

from . import catalog
from .client import extract_id, extract_version
from .errors import ApiError, DtDashError
from .version import DASHBOARD_CONTENT_VERSION

OK = "ok"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"

STATUS_ICON = {OK: "[ ok ]", WARN: "[warn]", FAIL: "[FAIL]", SKIP: "[skip]"}

# DQL sintetica: valida execute/poll sem varrer bucket algum (custo zero de scan)
SYNTHETIC_DQL = 'data record(dtdash = "selftest")'
INVALID_DQL = "fetch logs | filtre isso ai"


@dataclass
class Check:
    check_id: str
    title: str
    status: str = SKIP
    detail: str = ""
    elapsed: float = 0.0
    data: dict = field(default_factory=dict)
    hint: str = ""

    def to_dict(self):
        return {
            "id": self.check_id,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "elapsed": round(self.elapsed, 3),
            "data": self.data,
            "hint": self.hint,
        }


class SelfTestReport(object):
    def __init__(self, tenant="", write_mode=False):
        self.tenant = tenant
        self.write_mode = write_mode
        self.checks = []
        self.started_at = time.time()

    def add(self, check):
        self.checks.append(check)
        return check

    def counts(self):
        out = {OK: 0, WARN: 0, FAIL: 0, SKIP: 0}
        for check in self.checks:
            out[check.status] = out.get(check.status, 0) + 1
        return out

    @property
    def ok(self):
        return self.counts()[FAIL] == 0

    def to_dict(self):
        return {
            "tenant": self.tenant,
            "writeMode": self.write_mode,
            "ok": self.ok,
            "counts": self.counts(),
            "durationSeconds": round(time.time() - self.started_at, 2),
            "checks": [c.to_dict() for c in self.checks],
        }

    def to_text(self):
        lines = []
        lines.append("=" * 78)
        lines.append("dtdash selftest - tenant %s (%s)"
                     % (self.tenant or "?", "leitura+escrita" if self.write_mode else "somente leitura"))
        lines.append("=" * 78)
        for check in self.checks:
            lines.append("%s %-26s %s" % (STATUS_ICON.get(check.status, "[????]"),
                                          check.check_id, check.title))
            if check.detail:
                for piece in _wrap(check.detail, 66):
                    lines.append("       %s" % piece)
            if check.hint and check.status in (WARN, FAIL):
                for piece in _wrap("-> %s" % check.hint, 66):
                    lines.append("       %s" % piece)
        counts = self.counts()
        lines.append("-" * 78)
        lines.append("%d ok, %d aviso(s), %d falha(s), %d ignorado(s) em %.1fs"
                     % (counts[OK], counts[WARN], counts[FAIL], counts[SKIP],
                        time.time() - self.started_at))
        if not self.write_mode:
            lines.append("Use --write para exercitar tambem a criacao de segment e dashboard.")
        return "\n".join(lines)


def _wrap(text, width):
    words = str(text).split()
    line, out = "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = ("%s %s" % (line, word)).strip()
    if line:
        out.append(line)
    return out or [""]


class SelfTest(object):
    def __init__(self, client, report=None):
        self.client = client
        self.profile = client.profile
        self.report = report or SelfTestReport(tenant=self.profile.name)
        self._created_segments = []
        self._created_documents = []

    # ------------------------------------------------------------------ infra
    def _run(self, check_id, title, func, hint=""):
        check = Check(check_id=check_id, title=title, hint=hint)
        started = time.time()
        try:
            status, detail, data = func()
            check.status = status
            check.detail = detail
            check.data = data or {}
        except ApiError as exc:
            check.status = FAIL
            check.detail = str(exc)
        except DtDashError as exc:
            check.status = FAIL
            check.detail = str(exc)
        except Exception as exc:  # noqa: BLE001 - o selftest nunca deve abortar
            check.status = FAIL
            check.detail = "erro inesperado: %s" % exc
        check.elapsed = time.time() - started
        return self.report.add(check)

    # ------------------------------------------------------------------- run
    def run(self, write=False, share=True, cleanup=True, queries=True, metrics=True):
        self.report.write_mode = write

        self._run("config", "Perfil e credenciais", self.check_config,
                  hint="revise 'dtdash tenants add' e a variavel de ambiente da credencial")
        auth = self._run("auth", "Autenticacao na plataforma", self.check_auth,
                         hint="verifique o token/OAuth e os escopos concedidos")
        if auth.status == FAIL:
            self.report.add(Check("abortado", "Demais verificacoes ignoradas", SKIP,
                                  "sem autenticacao nao ha o que testar"))
            return self.report

        self._run("documents.read", "Document API - listagem", self.check_documents_read,
                  hint="escopo document:documents:read")
        self._run("segments.read", "Filter segments - listagem", self.check_segments_read,
                  hint="escopo storage:filter-segments:read")
        self._run("grail.execute", "Grail - execute/poll (DQL sintetica)", self.check_grail_execute,
                  hint="escopos storage:*:read")
        self._run("grail.verify", "Grail - query:verify", self.check_grail_verify,
                  hint="sem esse endpoint o dtdash valida executando com limit")
        self._run("grail.dataobjects", "Grail - data objects disponiveis",
                  self.check_data_objects)
        self._run("grail.dps", "Consumo DPS (dt.system.events)", self.check_dps,
                  hint="escopo storage:system:read")
        if metrics:
            self._run("metrics.catalog", "Metricas do catalogo existentes no tenant",
                      self.check_metrics, hint="tiles com metrica ausente serao sinalizados")
        if queries:
            self._run("dql.blueprints", "Sintaxe das DQL de todos os blueprints",
                      self.check_blueprint_queries)

        if write:
            try:
                self._run("segments.write", "Filter segments - criar e ler",
                          self.check_segment_write,
                          hint="escopos storage:filter-segments:write e :share")
                self._run("documents.write", "Document API - criar dashboard e ler de volta",
                          self.check_document_write,
                          hint="escopo document:documents:write")
                self._run("tile.segments", "Propriedade 'segments' do tile sobrevive ao round-trip",
                          self.check_tile_segments,
                          hint="se falhar, use --segment-mode dql ao gerar dashboards")
                if share:
                    self._run("documents.share", "Compartilhamento com o ambiente",
                              self.check_share,
                              hint="escopo document:environment-shares:write")
            finally:
                if cleanup:
                    self._run("cleanup", "Remocao dos objetos temporarios", self.check_cleanup,
                              hint="remova manualmente os objetos com prefixo dtdash-selftest")
        else:
            for check_id, title in (
                ("segments.write", "Filter segments - criar e ler"),
                ("documents.write", "Document API - criar dashboard e ler de volta"),
                ("tile.segments", "Propriedade 'segments' do tile sobrevive ao round-trip"),
                ("documents.share", "Compartilhamento com o ambiente"),
            ):
                self.report.add(Check(check_id, title, SKIP, "modo somente leitura (use --write)"))
        return self.report

    # --------------------------------------------------------------- leitura
    def check_config(self):
        profile = self.profile
        if not profile.platform_url:
            return FAIL, "perfil sem platform_url", {}
        if not profile.has_credentials():
            return FAIL, "credencial nao encontrada no ambiente", {
                "authMethod": profile.auth_method}
        return OK, "%s (auth=%s)" % (profile.platform_url, profile.auth_method), {
            "platformUrl": profile.platform_url,
            "environmentId": profile.environment_id,
            "authMethod": profile.auth_method,
        }

    def check_auth(self):
        token = self.client.tokens.access_token()
        if not token:
            return FAIL, "nenhum token obtido", {}
        prefix = token[:8]
        if self.profile.auth_method == "oauth":
            return OK, "access token obtido no SSO (prefixo %s...)" % prefix, {"prefix": prefix}
        return OK, "platform token carregado (prefixo %s...)" % prefix, {"prefix": prefix}

    def check_documents_read(self):
        documents = self.client.list_documents(page_size=5)
        return OK, "%d dashboard(s) visiveis" % len(documents), {"sample": [
            {"id": extract_id(d), "name": d.get("name")} for d in documents[:3]
        ]}

    def check_segments_read(self):
        segments = self.client.list_segments()
        keys = sorted({k for s in segments[:5] if isinstance(s, dict) for k in s})[:12]
        return OK, "%d segment(s) visiveis; campos: %s" % (len(segments), ", ".join(keys) or "-"), {
            "count": len(segments), "fields": keys,
        }

    def check_grail_execute(self):
        outcome = self.client.execute_query(SYNTHETIC_DQL, max_records=1)
        records = outcome.get("records") or []
        if not records:
            return WARN, "execucao respondeu sem registros (state=%s)" % outcome.get("state"), {
                "state": outcome.get("state")}
        return OK, "state=%s, registro devolvido: %s" % (outcome.get("state"), records[0]), {
            "state": outcome.get("state"), "record": records[0]}

    def check_grail_verify(self):
        good = self.client.verify_query(SYNTHETIC_DQL)
        if good is None:
            return WARN, "endpoint query:verify indisponivel neste tenant", {"available": False}
        bad = self.client.verify_query(INVALID_DQL)
        detail = "valida=%s; DQL invalida rejeitada=%s" % (
            good.get("valid"), (bad or {}).get("valid") is False)
        status = OK if good.get("valid") and (bad or {}).get("valid") is False else WARN
        return status, detail, {"available": True, "good": good, "bad": bad}

    def check_data_objects(self):
        objects = self.client.data_objects()
        if not objects:
            return WARN, "nenhum data object retornado", {}
        esperado = ["logs", "spans", "events", "bizevents", "user.events",
                    "security.events", "dt.davis.problems", "dt.system.events"]
        ausentes = [o for o in esperado if o not in objects]
        detail = "%d objeto(s); ausentes entre os usuais: %s" % (
            len(objects), ", ".join(ausentes) or "nenhum")
        return OK, detail, {"count": len(objects), "missing": ausentes,
                            "sample": objects[:15]}

    def check_dps(self):
        from .capabilities import DPS_PROBE_DQL

        outcome = self.client.execute_query(DPS_PROBE_DQL, max_records=10)
        records = outcome.get("records") or []
        if records:
            tipos = [r.get("event.type") for r in records if r.get("event.type")]
            return OK, "consumo DPS detectado: %s" % ", ".join(tipos[:5]), {
                "dps": True, "eventTypes": tipos}
        return WARN, ("sem eventos de billing nas ultimas 24h - isso NAO prova ausencia de "
                      "licenca (eventos medem consumo, nao entitlement)"), {"dps": False}

    def check_metrics(self):
        keys = sorted({m for bp in catalog.CATALOG for m in bp.metrics})
        if not keys:
            return SKIP, "catalogo sem metricas", {}
        listed = ", ".join('"%s"' % k for k in keys)
        outcome = self.client.execute_query(
            "metrics\n| filter in(metric.key, {%s})\n| fields metric.key" % listed,
            max_records=500,
        )
        found = {r.get("metric.key") for r in outcome.get("records") or []}
        missing = [k for k in keys if k not in found]
        afetados = sorted({bp.bp_id for bp in catalog.CATALOG
                           if set(bp.metrics) & set(missing)})
        status = OK if not missing else WARN
        detail = "%d de %d metricas presentes" % (len(keys) - len(missing), len(keys))
        if missing:
            detail += "; ausentes: %s" % ", ".join(missing[:8])
            detail += " (blueprints afetados: %s)" % ", ".join(afetados[:8])
        return status, detail, {"missing": missing, "affectedBlueprints": afetados}

    def check_blueprint_queries(self):
        available = self.client.verify_query(SYNTHETIC_DQL)
        if available is None:
            return SKIP, "query:verify indisponivel; use 'dtdash plan --validate-live'", {}
        invalidas = []
        total = 0
        for blueprint in catalog.CATALOG:
            query = blueprint.query
            if not query:
                continue
            total += 1
            try:
                result = self.client.verify_query(query)
            except ApiError as exc:
                invalidas.append({"blueprint": blueprint.bp_id, "erro": str(exc)[:160]})
                continue
            if result is not None and not result.get("valid"):
                message = ""
                for notification in result.get("notifications") or []:
                    if notification.get("message"):
                        message = notification["message"]
                        break
                invalidas.append({"blueprint": blueprint.bp_id, "erro": message[:160]})
        status = OK if not invalidas else FAIL
        detail = "%d de %d queries validas" % (total - len(invalidas), total)
        if invalidas:
            detail += "; problemas: %s" % "; ".join(
                "%s (%s)" % (i["blueprint"], i["erro"]) for i in invalidas[:5]
            )
        return status, detail, {"invalid": invalidas, "total": total}

    # --------------------------------------------------------------- escrita
    def _stamp(self):
        return "dtdash-selftest-%s" % time.strftime("%Y%m%d-%H%M%S")

    def check_segment_write(self):
        name = self._stamp()
        payload = {
            "name": name,
            "description": "objeto temporario criado pelo 'dtdash selftest' - pode ser removido",
            "isPublic": False,
            "includes": [
                {"dataObject": "logs", "filter": 'dt.system.bucket == "default_logs"'}
            ],
        }
        created = self.client.create_segment(payload)
        uid = extract_id(created)
        if not uid:
            return FAIL, "resposta de criacao sem identificador: %s" % list(created)[:8], {
                "response": created}
        self._created_segments.append((uid, extract_version(created)))
        detail = "segment criado (uid=%s)" % uid
        try:
            read_back = self.client.get_segment(uid)
            includes = read_back.get("includes") or []
            detail += "; leitura de volta com %d include(s)" % len(includes)
        except ApiError as exc:
            return WARN, detail + "; leitura individual falhou: %s" % exc, {"uid": uid}
        return OK, detail, {"uid": uid, "idKey": _id_key(created)}

    def _selftest_content(self, segment_uids=None):
        tile = {
            "type": "data",
            "title": "dtdash selftest",
            "query": SYNTHETIC_DQL,
            "visualization": "table",
            "visualizationSettings": {},
            "querySettings": {},
        }
        if segment_uids:
            tile["segments"] = list(segment_uids)
        return {
            "version": DASHBOARD_CONTENT_VERSION,
            "variables": [],
            "tiles": {
                "1": {"type": "markdown",
                      "content": "# dtdash selftest\nDashboard temporario de verificacao."},
                "2": tile,
            },
            "layouts": {
                "1": {"x": 0, "y": 0, "w": 24, "h": 2},
                "2": {"x": 0, "y": 2, "w": 12, "h": 6},
            },
        }

    def check_document_write(self):
        name = self._stamp()
        created = self.client.create_document(
            name=name, content=self._selftest_content(), doc_type="dashboard",
            description="objeto temporario criado pelo 'dtdash selftest'", is_private=True,
        )
        document_id = extract_id(created)
        if not document_id:
            return FAIL, "resposta de criacao sem identificador: %s" % list(created)[:8], {
                "response": created}
        self._created_documents.append((document_id, extract_version(created)))
        detail = "dashboard criado (id=%s)" % document_id
        content = self.client.get_document_content(document_id)
        tiles = (content or {}).get("tiles") or {}
        if len(tiles) != 2:
            return WARN, detail + "; round-trip devolveu %d tile(s) (esperado 2)" % len(tiles), {
                "documentId": document_id, "url": self.profile.dashboard_url(document_id)}
        return OK, detail + "; conteudo lido de volta com %d tiles" % len(tiles), {
            "documentId": document_id,
            "idKey": _id_key(created),
            "url": self.profile.dashboard_url(document_id),
        }

    def check_tile_segments(self):
        if not self._created_segments:
            return SKIP, "nenhum segment temporario disponivel", {}
        uid = self._created_segments[0][0]
        name = "%s-seg" % self._stamp()
        created = self.client.create_document(
            name=name, content=self._selftest_content([uid]), doc_type="dashboard",
            is_private=True,
        )
        document_id = extract_id(created)
        if not document_id:
            return FAIL, "criacao sem identificador", {"response": created}
        self._created_documents.append((document_id, extract_version(created)))
        content = self.client.get_document_content(document_id) or {}
        tile = (content.get("tiles") or {}).get("2") or {}
        segments = tile.get("segments")
        if segments == [uid]:
            return OK, "a propriedade 'segments' do tile foi preservada", {
                "segments": segments}
        return WARN, ("a propriedade 'segments' voltou como %r - gere os dashboards com "
                      "--segment-mode dql para embutir o filtro na query" % (segments,)), {
            "segments": segments}

    def check_share(self):
        if not self._created_documents:
            return SKIP, "nenhum dashboard temporario disponivel", {}
        document_id = self._created_documents[0][0]
        result = self.client.share_document_with_environment(document_id)
        method = (result or {}).get("method") or (result or {}).get("status") or "ok"
        return OK, "compartilhamento aceito (%s)" % method, {"result": result}

    def check_cleanup(self):
        removed, failed = [], []
        for document_id, version in list(self._created_documents):
            try:
                self.client.delete_document(document_id, version=version)
                removed.append("dashboard %s" % document_id)
            except ApiError as exc:
                try:
                    self.client.delete_document(document_id)
                    removed.append("dashboard %s" % document_id)
                except ApiError:
                    failed.append("dashboard %s (%s)" % (document_id, exc))
        for uid, version in list(self._created_segments):
            try:
                self.client.delete_segment(uid, version=version)
                removed.append("segment %s" % uid)
            except ApiError as exc:
                try:
                    self.client.delete_segment(uid)
                    removed.append("segment %s" % uid)
                except ApiError:
                    failed.append("segment %s (%s)" % (uid, exc))
        self._created_documents = []
        self._created_segments = []
        if failed:
            return WARN, "removidos: %s; PENDENTES: %s" % (
                ", ".join(removed) or "nenhum", ", ".join(failed)), {"failed": failed}
        return OK, "removidos: %s" % (", ".join(removed) or "nenhum"), {"removed": removed}


def _id_key(payload):
    """Chave em que a API devolveu o identificador (antes da normalizacao)."""

    if isinstance(payload, dict) and payload.get("_idKey"):
        return payload["_idKey"]
    return "?"
