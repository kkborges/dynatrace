"""Interface de linha de comando do dtdash."""

import argparse
import json
import os
import sys

from . import catalog
from .config import Config, TenantProfile, Workspace
from .errors import DtDashError
from .knowledge import DEFAULT_DOC_SOURCES, DEFAULT_GITHUB_SOURCES, KnowledgeSync
from .preview import render_text
from .service import DashboardService
from .version import __version__

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INVALID = 2


# ------------------------------------------------------------------ utilidades
def _out(message=""):
    sys.stdout.write("%s\n" % message)


def _err(message):
    sys.stderr.write("%s\n" % message)


def _read_text(args):
    if getattr(args, "file", None):
        with open(args.file, "r", encoding="utf-8") as handle:
            return handle.read()
    text = " ".join(getattr(args, "description", []) or []).strip()
    if text:
        return text
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise DtDashError("informe a descricao do dashboard (texto, --file ou stdin)")


def _service(args):
    workspace = Workspace(getattr(args, "workspace", None))
    workspace.ensure()
    return DashboardService(workspace, Config.load(workspace))


def _confirm(question, assume_yes=False):
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        raise DtDashError("execucao nao interativa: use --yes para confirmar")
    answer = input("%s [s/N] " % question).strip().lower()
    return answer in ("s", "sim", "y", "yes")


# ------------------------------------------------------------------- comandos
def cmd_init(args):
    workspace = Workspace(args.workspace)
    workspace.ensure()
    config = Config.load(workspace)
    path = config.save()
    _out("workspace pronto em %s" % workspace.root)
    _out("configuracao: %s" % path)
    _out("pastas: dashboards/library, dashboards/clients, knowledge/, examples/")
    _out("")
    _out("proximos passos:")
    _out("  1. dtdash tenants add --name meu-tenant --environment-id abc12345")
    _out("     export DT_PLATFORM_TOKEN=dt0s16....")
    _out("  2. dtdash kb sync")
    _out('  3. dtdash plan "descreva aqui a necessidade do dashboard"')
    return EXIT_OK


def cmd_tenants(args):
    workspace = Workspace(args.workspace)
    config = Config.load(workspace)

    if args.tenants_command == "list":
        if not config.tenant_names():
            _out("nenhum tenant configurado")
            return EXIT_OK
        default = config.setting("default_tenant")
        for name in config.tenant_names():
            profile = config.get_tenant(name)
            flag = "*" if name == default else " "
            _out("%s %-20s %-45s auth=%-15s cred=%s"
                 % (flag, name, profile.platform_url, profile.auth_method,
                    "ok" if profile.has_credentials() else "ausente"))
        return EXIT_OK

    if args.tenants_command == "add":
        profile = TenantProfile(
            name=args.name,
            environment_id=args.environment_id or "",
            platform_url=args.platform_url or "",
            environment_url=args.environment_url or "",
            auth_method=args.auth,
            client_name=args.client or args.name,
            oauth_account_urn=args.account_urn or "",
        )
        if args.token_env:
            profile.platform_token_env = args.token_env
        if args.client_id_env:
            profile.oauth_client_id_env = args.client_id_env
        if args.client_secret_env:
            profile.oauth_client_secret_env = args.client_secret_env
        config.put_tenant(profile)
        config.save()
        _out("tenant '%s' salvo (%s)" % (profile.name, profile.platform_url))
        if not profile.has_credentials():
            _err("aviso: credenciais nao encontradas no ambiente (%s)"
                 % (profile.platform_token_env if profile.auth_method == "platform_token"
                    else profile.oauth_client_id_env))
        return EXIT_OK

    if args.tenants_command == "remove":
        config.remove_tenant(args.name)
        config.save()
        _out("tenant '%s' removido" % args.name)
        return EXIT_OK

    if args.tenants_command == "use":
        config.set_default_tenant(args.name)
        config.save()
        _out("tenant padrao: %s" % args.name)
        return EXIT_OK

    if args.tenants_command == "test":
        service = DashboardService(workspace, config)
        caps = service.capabilities(args.name, probe=True, cache=False)
        _out("online .........: %s" % caps.online)
        _out("Grail consultavel: %s" % caps.grail_queryable)
        _out("licenca ........: %s" % caps.license_label())
        _out("data objects ...: %d" % len(caps.data_objects))
        if caps.dps_event_types:
            _out("consumo DPS ....: %s" % ", ".join(caps.dps_event_types[:6]))
        for error in caps.errors:
            _err("erro: %s" % error)
        return EXIT_OK if caps.online else EXIT_ERROR

    raise DtDashError("subcomando de tenants desconhecido")


def cmd_kb(args):
    service = _service(args)
    if args.kb_command == "sync":
        only = args.only.split(",") if args.only else None
        result = service.sync_knowledge(
            github=not args.docs_only, docs=not args.github_only, only=only
        )
        _out(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK
    if args.kb_command == "status":
        stats = service.knowledge().stats()
        _out(json.dumps(stats, ensure_ascii=False, indent=2))
        _out("")
        _out("fontes GitHub disponiveis:")
        for source in DEFAULT_GITHUB_SOURCES:
            _out("  %-26s %s%s" % (source["name"], source["url"],
                                   "" if source.get("enabled", True) else "  (desativada)"))
        _out("fontes de documentacao:")
        for source in DEFAULT_DOC_SOURCES:
            _out("  %-26s %s" % (source["name"], source["url"]))
        return EXIT_OK
    if args.kb_command == "search":
        hits = service.knowledge().search(" ".join(args.query), limit=args.limit)
        if not hits:
            _out("nenhum resultado")
        for hit in hits:
            _out("[%s] %-38s %s" % (hit.doc.source, hit.doc.title[:38], hit.doc.path))
            _out("      %s" % hit.snippet[:160])
        return EXIT_OK
    if args.kb_command == "add":
        sync = KnowledgeSync(service.workspace)
        for path in args.paths:
            target = sync.import_path(path)
            _out("importado: %s" % target)
        service.knowledge(rebuild=True)
        _out("indice atualizado: %s" % service.knowledge().stats()["documents"])
        return EXIT_OK
    raise DtDashError("subcomando de kb desconhecido")


def cmd_plan(args):
    service = _service(args)
    text = _read_text(args)
    outcome = service.plan(
        text,
        tenant=args.tenant,
        name=args.name,
        audience=args.audience,
        segment_mode=args.segment_mode,
        max_tiles=args.max_tiles,
        base_template=args.base,
        probe=not args.offline,
        validate_live=args.validate_live,
        client_name=args.client,
        extra_domains=args.domain or None,
    )
    proposal = outcome["proposal"]
    report = outcome["report"]
    if not args.quiet:
        _out(outcome["text"])
        _out("")
    _out("proposta ...: %s" % proposal.proposal_id)
    _out("previa .....: %s" % proposal.preview_path())
    _out("json .......: %s" % proposal.file("dashboard.json"))
    _out("validacao ..: %d erro(s), %d aviso(s)" % (len(report.errors), len(report.warnings)))
    _out("")
    _out("para publicar no tenant:  dtdash approve %s --yes" % proposal.proposal_id)
    return EXIT_INVALID if report.errors else EXIT_OK


def cmd_preview(args):
    service = _service(args)
    proposal = (
        service.proposals.get(args.proposal) if args.proposal else service.proposals.latest()
    )
    if args.path:
        _out(proposal.preview_path())
        return EXIT_OK
    if args.json:
        _out(json.dumps(proposal.document(), ensure_ascii=False, indent=2))
        return EXIT_OK
    spec = proposal.spec()
    _out(render_text(spec))
    _out("")
    _out("previa HTML: %s" % proposal.preview_path())
    return EXIT_OK


def cmd_proposals(args):
    service = _service(args)
    items = service.proposals.list(limit=args.limit)
    if not items:
        _out("nenhuma proposta")
        return EXIT_OK
    for proposal in items:
        meta = proposal.meta
        _out("%-34s %-10s %-28s tiles=%s"
             % (proposal.proposal_id, meta.get("status", "?"), (meta.get("name") or "")[:28],
                meta.get("tiles", "?")))
    return EXIT_OK


def cmd_approve(args):
    service = _service(args)
    proposal = (
        service.proposals.get(args.proposal) if args.proposal else service.proposals.latest()
    )
    spec = proposal.spec()
    tenant = args.tenant or spec.tenant
    profile = service.tenant(tenant, required=True)

    _out("dashboard ..: %s" % spec.name)
    _out("tenant .....: %s (%s)" % (profile.name, profile.platform_url))
    _out("tiles ......: %d" % len(spec.data_tiles()))
    if spec.segments:
        _out("segments ...: %s" % ", ".join(s.name for s in spec.segments))
    if not args.dry_run:
        if not _confirm("criar este dashboard no tenant agora?", args.yes):
            _out("cancelado")
            return EXIT_OK

    outcome = service.approve(
        proposal.proposal_id, tenant=tenant, share=args.share,
        save_template=not args.no_template, scope=args.scope, force=args.force,
        dry_run=args.dry_run, client_name=args.client,
    )
    result = outcome["result"]
    _out("")
    for segment in result.segments:
        _out("segment %-30s uid=%-38s %s"
             % (segment.get("name", "")[:30], segment.get("uid", ""),
                "criado" if segment.get("created") else segment.get("error", "reutilizado")))
    _out("dashboard id: %s" % result.document_id)
    _out("url ........: %s" % result.url)
    if result.template_path:
        _out("template ...: %s" % result.template_path)
    for warning in result.warnings:
        _err("aviso: %s" % warning)
    return EXIT_OK


def cmd_reject(args):
    service = _service(args)
    proposal = service.reject(args.proposal, reason=args.reason or "")
    _out("proposta %s marcada como rejeitada" % proposal.proposal_id)
    return EXIT_OK


def cmd_templates(args):
    service = _service(args)
    if args.templates_command == "list":
        entries = service.library.entries(scope=args.scope, client=args.client)
        if not entries:
            _out("nenhum template")
            return EXIT_OK
        for entry in entries:
            _out("%-9s %-22s %-38s tiles=%-3s %s"
                 % (entry["scope"], entry["client"] or "-", entry["name"][:38],
                    entry["tiles"], entry["ref"]))
        return EXIT_OK
    if args.templates_command == "show":
        document = service.library.load(args.ref)
        _out(json.dumps(document, ensure_ascii=False, indent=2))
        return EXIT_OK
    if args.templates_command == "save":
        path = service.save_as_template(args.proposal, scope=args.scope, client=args.client)
        _out("template salvo em %s" % path)
        return EXIT_OK
    if args.templates_command == "import":
        with open(args.path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        path = service.library.save(
            document, scope=args.scope, client=args.client, origin="importado"
        )
        _out("template importado para %s" % path)
        return EXIT_OK
    if args.templates_command == "reindex":
        _out("indice: %s" % service.library.reindex())
        return EXIT_OK
    raise DtDashError("subcomando de templates desconhecido")


def cmd_validate(args):
    service = _service(args)
    with open(args.path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    from .validator import validate_document

    report = validate_document(document)
    for finding in report.findings:
        _out("%-8s %-5s %s" % (finding.level, finding.tile or "-", finding.message))
    _out("")
    _out("%d erro(s), %d aviso(s)" % (len(report.errors), len(report.warnings)))
    if args.tenant:
        from .builder import dashboard_to_spec
        from .validator import validate_queries_live

        spec = dashboard_to_spec(document)
        results = validate_queries_live(spec, service.client_for(args.tenant))
        for entry in results:
            _out("%-6s %-30s %s" % (entry.get("tile"), (entry.get("title") or "")[:30],
                                    entry.get("status")))
    return EXIT_INVALID if report.errors else EXIT_OK


def cmd_catalog(args):
    for blueprint in catalog.CATALOG:
        if args.domain and blueprint.domain != args.domain:
            continue
        _out("%-28s %-11s %-18s %s"
             % (blueprint.bp_id, blueprint.domain, blueprint.visualization, blueprint.title))
    return EXIT_OK


def cmd_serve(args):
    from .server import serve

    service = _service(args)
    serve(service, host=args.host, port=args.port)
    return EXIT_OK


def cmd_doctor(args):
    service = _service(args)
    _out("dtdash %s" % __version__)
    _out("workspace ..: %s" % service.workspace.root)
    _out("config .....: %s" % service.workspace.config_path)
    knowledge = service.knowledge()
    stats = knowledge.stats()
    _out("conhecimento: %d documentos (%s)"
         % (stats["documents"], ", ".join("%s=%d" % kv for kv in sorted(stats["bySource"].items()))))
    _out("templates ..: %d" % len(service.library.entries()))
    _out("propostas ..: %d" % len(service.proposals.ids()))
    tenants = service.config.tenant_names()
    _out("tenants ....: %s" % (", ".join(tenants) or "(nenhum)"))
    for name in tenants:
        profile = service.config.get_tenant(name)
        _out("  - %-18s %-42s credenciais=%s"
             % (name, profile.platform_url, "ok" if profile.has_credentials() else "AUSENTES"))
    if stats["documents"] < 5:
        _err("dica: rode 'dtdash kb sync' para baixar a base de conhecimento oficial")
    return EXIT_OK


# --------------------------------------------------------------------- parser
def build_parser():
    parser = argparse.ArgumentParser(
        prog="dtdash",
        description="Gera, previsualiza e publica dashboards da plataforma Dynatrace "
                    "a partir de uma descricao em linguagem natural.",
    )
    parser.add_argument("--version", action="version", version="dtdash %s" % __version__)
    parser.add_argument("--workspace", help="raiz do workspace (padrao: repositorio atual)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="prepara o workspace").set_defaults(func=cmd_init)

    tenants = sub.add_parser("tenants", help="gerencia perfis de tenant")
    tenants.set_defaults(func=cmd_tenants)
    tsub = tenants.add_subparsers(dest="tenants_command", required=True)
    tsub.add_parser("list", help="lista tenants")
    add = tsub.add_parser("add", help="adiciona/atualiza um tenant")
    add.add_argument("--name", required=True)
    add.add_argument("--environment-id", help="ex.: abc12345")
    add.add_argument("--platform-url", help="https://abc12345.apps.dynatrace.com")
    add.add_argument("--environment-url", help="https://abc12345.live.dynatrace.com")
    add.add_argument("--auth", choices=["platform_token", "oauth"], default="platform_token")
    add.add_argument("--account-urn", help="urn:dtaccount:<uuid> (OAuth)")
    add.add_argument("--client", help="nome do cliente/empresa")
    add.add_argument("--token-env", help="variavel com o platform token")
    add.add_argument("--client-id-env")
    add.add_argument("--client-secret-env")
    remove = tsub.add_parser("remove", help="remove um tenant")
    remove.add_argument("name")
    use = tsub.add_parser("use", help="define o tenant padrao")
    use.add_argument("name")
    test = tsub.add_parser("test", help="testa conexao e capacidades")
    test.add_argument("name", nargs="?")

    kb = sub.add_parser("kb", help="base de conhecimento")
    kb.set_defaults(func=cmd_kb)
    ksub = kb.add_subparsers(dest="kb_command", required=True)
    sync = ksub.add_parser("sync", help="baixa docs e repositorios oficiais Dynatrace")
    sync.add_argument("--only", help="lista de fontes separadas por virgula")
    sync.add_argument("--github-only", action="store_true")
    sync.add_argument("--docs-only", action="store_true")
    ksub.add_parser("status", help="mostra o indice e as fontes")
    search = ksub.add_parser("search", help="busca na base")
    search.add_argument("query", nargs="+")
    search.add_argument("--limit", type=int, default=8)
    kadd = ksub.add_parser("add", help="importa arquivos/pastas de exemplo")
    kadd.add_argument("paths", nargs="+")

    plan = sub.add_parser("plan", help="gera a proposta de dashboard e a previa")
    plan.set_defaults(func=cmd_plan)
    plan.add_argument("description", nargs="*", help="descricao da necessidade")
    plan.add_argument("--file", help="arquivo com a descricao")
    plan.add_argument("-t", "--tenant")
    plan.add_argument("--name", help="nome do dashboard")
    plan.add_argument("--client", help="nome do cliente")
    plan.add_argument("--audience", choices=["exec", "sre", "dev", "finops"])
    plan.add_argument("--segment-mode", choices=["tile", "dql", "both"], default="tile")
    plan.add_argument("--max-tiles", type=int)
    plan.add_argument("--base", help="template base (ref ou nome)")
    plan.add_argument("--domain", action="append", help="forca um dominio adicional")
    plan.add_argument("--offline", action="store_true", help="nao consulta o tenant")
    plan.add_argument("--validate-live", action="store_true",
                      help="valida as DQL executando no tenant")
    plan.add_argument("--quiet", action="store_true")

    preview = sub.add_parser("preview", help="mostra a previa de uma proposta")
    preview.set_defaults(func=cmd_preview)
    preview.add_argument("proposal", nargs="?")
    preview.add_argument("--path", action="store_true", help="imprime o caminho do HTML")
    preview.add_argument("--json", action="store_true", help="imprime o JSON do dashboard")

    proposals = sub.add_parser("proposals", help="lista propostas")
    proposals.set_defaults(func=cmd_proposals)
    proposals.add_argument("--limit", type=int, default=20)

    approve = sub.add_parser("approve", help="aprova e cria o dashboard no tenant")
    approve.set_defaults(func=cmd_approve)
    approve.add_argument("proposal", nargs="?")
    approve.add_argument("-t", "--tenant")
    approve.add_argument("--client")
    approve.add_argument("--share", action="store_true",
                         help="compartilha com todo o ambiente (leitura)")
    approve.add_argument("--scope", choices=["clients", "library"], default="clients")
    approve.add_argument("--no-template", action="store_true",
                         help="nao salva copia em dashboards/")
    approve.add_argument("--force", action="store_true", help="publica mesmo com erros")
    approve.add_argument("--dry-run", action="store_true")
    approve.add_argument("--yes", action="store_true")

    reject = sub.add_parser("reject", help="marca a proposta como rejeitada")
    reject.set_defaults(func=cmd_reject)
    reject.add_argument("proposal", nargs="?")
    reject.add_argument("--reason")

    templates = sub.add_parser("templates", help="biblioteca de templates")
    templates.set_defaults(func=cmd_templates)
    tpl = templates.add_subparsers(dest="templates_command", required=True)
    tlist = tpl.add_parser("list")
    tlist.add_argument("--scope", choices=["clients", "library"])
    tlist.add_argument("--client")
    tshow = tpl.add_parser("show")
    tshow.add_argument("ref")
    tsave = tpl.add_parser("save", help="salva uma proposta como template")
    tsave.add_argument("proposal", nargs="?")
    tsave.add_argument("--scope", choices=["clients", "library"], default="library")
    tsave.add_argument("--client")
    timport = tpl.add_parser("import", help="importa um JSON de dashboard existente")
    timport.add_argument("path")
    timport.add_argument("--scope", choices=["clients", "library"], default="library")
    timport.add_argument("--client")
    tpl.add_parser("reindex")

    validate = sub.add_parser("validate", help="valida um JSON de dashboard")
    validate.set_defaults(func=cmd_validate)
    validate.add_argument("path")
    validate.add_argument("-t", "--tenant", help="valida tambem as DQL no tenant")

    catalog_cmd = sub.add_parser("catalog", help="lista os blueprints disponiveis")
    catalog_cmd.set_defaults(func=cmd_catalog)
    catalog_cmd.add_argument("--domain")

    serve = sub.add_parser("serve", help="interface web")
    serve.set_defaults(func=cmd_serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    sub.add_parser("doctor", help="diagnostico do ambiente").set_defaults(func=cmd_doctor)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return EXIT_ERROR
    try:
        return args.func(args)
    except DtDashError as exc:
        _err("erro: %s" % exc)
        return EXIT_ERROR
    except KeyboardInterrupt:  # pragma: no cover
        _err("interrompido")
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
