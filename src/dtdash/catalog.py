"""Catalogo de blueprints de tiles.

Cada blueprint e um tile pronto - pergunta que responde, DQL validada contra os
padroes oficiais (skills `Dynatrace/dynatrace-for-ai`) e visualizacao adequada ao
formato do resultado. O planner escolhe blueprints a partir da descricao do
solicitante e das capacidades do tenant.
"""

from dataclasses import dataclass, field

# --------------------------------------------------------------------- campos
# Mapeamento dimensao -> campo por modelo de dados (candidatos em ordem de
# preferencia; o planner verifica no tenant com `describe` quando online).
FIELD_MAP = {
    "cluster": {
        "logs": ["k8s.cluster.name"],
        "spans": ["k8s.cluster.name"],
        "events": ["k8s.cluster.name"],
        "metrics": ["k8s.cluster.name"],
        "smartscape": ["k8s.cluster.name"],
        "dt.davis.problems": ["k8s.cluster.name"],
    },
    "namespace": {
        "logs": ["k8s.namespace.name"],
        "spans": ["k8s.namespace.name"],
        "events": ["k8s.namespace.name"],
        "metrics": ["k8s.namespace.name"],
        "smartscape": ["k8s.namespace.name"],
        "dt.davis.problems": ["k8s.namespace.name"],
    },
    "workload": {
        "logs": ["k8s.workload.name"],
        "spans": ["k8s.workload.name"],
        "metrics": ["k8s.workload.name"],
        "smartscape": ["k8s.workload.name"],
    },
    "service": {
        "logs": ["service.name", "dt.process_group.detected_name"],
        "spans": ["dt.service.name", "service.name"],
        "metrics": ["dt.service.name"],
        "smartscape": ["name"],
        "dt.davis.problems": ["dt.smartscape.service"],
    },
    "host": {
        "logs": ["host.name"],
        "spans": ["host.name"],
        "metrics": ["dt.smartscape.host"],
        "smartscape": ["name"],
    },
    "application": {
        "user.events": ["frontend.name"],
        "metrics": ["frontend.name"],
        "logs": ["application.name"],
    },
    "environment": {
        "logs": ["environment", "dt.host.group.id", "k8s.cluster.name"],
        "spans": ["environment", "dt.host.group.id"],
        "metrics": ["dt.host.group.id"],
        "smartscape": ["host.group.name"],
    },
    "costcenter": {
        "dt.system.events": ["dt.cost.costcenter"],
        "smartscape": ["dt.cost.costcenter"],
    },
}

# Objeto de dados usado para injecao de filtro por dominio
DOMAIN_FILTER_OBJECT = {
    "hosts": "metrics",
    "kubernetes": "metrics",
    "services": "metrics",
    "spans": "spans",
    "logs": "logs",
    "problems": "dt.davis.problems",
    "rum": "user.events",
    "security": "security.events",
    "bizevents": "bizevents",
    "dps": "dt.system.events",
    "database": "spans",
}


@dataclass
class Blueprint:
    bp_id: str
    domain: str
    signal: str                     # latency | traffic | errors | saturation | inventory | cost | context
    title: str
    question: str
    query: str
    visualization: str = "lineChart"
    source_kind: str = "fetch"      # fetch | timeseries | smartscape | none
    filter_object: str = ""         # modelo usado para injetar filtros
    width: int = 12
    height: int = 7
    section: str = ""
    requires: list = field(default_factory=list)     # data objects necessarios
    metrics: list = field(default_factory=list)      # chaves de metrica usadas
    keywords: list = field(default_factory=list)
    audiences: list = field(default_factory=lambda: ["sre", "dev", "exec", "finops"])
    priority: int = 50              # maior = mais importante para o dominio
    visualization_settings: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    dps_only: bool = False

    def filter_target(self):
        return self.filter_object or DOMAIN_FILTER_OBJECT.get(self.domain, "")


def _single(record_field, label, unit=None):
    settings = {
        "singleValue": {
            "recordField": record_field,
            "label": label,
            "colorThresholdTarget": "value",
            "alignment": "center",
            "isIconVisible": False,
        }
    }
    if unit:
        settings["unitsOverrides"] = [
            {
                "identifier": record_field,
                "unitCategory": unit[0],
                "baseUnit": unit[1],
                "displayUnit": None,
                "decimals": unit[2] if len(unit) > 2 else None,
                "suffix": "",
                "delimiter": False,
            }
        ]
    return settings


LINE = {"chartSettings": {"xAxisScaling": "analyzedTimeframe",
                          "legend": {"position": "bottom", "showLegend": True}}}
DONUT = {"chartSettings": {"circleChartSettings": {"valueType": "relative"}}}
BARS = {"chartSettings": {"categoryAxis": {"tickLayout": "horizontal"}}}


CATALOG = [
    # ================================================================= HOSTS
    Blueprint(
        bp_id="hosts.count",
        domain="hosts", signal="inventory",
        title="Hosts monitorados",
        question="Quantos hosts estao sob monitoramento?",
        query='smartscapeNodes "HOST"\n| summarize hosts = count()',
        visualization="singleValue", source_kind="smartscape", filter_object="smartscape",
        width=6, height=4, section="Infraestrutura",
        requires=[], keywords=["host", "hosts", "servidor", "servidores", "infraestrutura", "infra"],
        priority=70, visualization_settings=_single("hosts", "Hosts"),
    ),
    Blueprint(
        bp_id="hosts.cpu_trend",
        domain="hosts", signal="saturation",
        title="CPU por host (media)",
        question="Como esta o consumo de CPU dos hosts no periodo?",
        query=("timeseries cpu = avg(dt.host.cpu.usage), by:{dt.smartscape.host}\n"
               "| fieldsAdd host = getNodeName(dt.smartscape.host)"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Infraestrutura",
        metrics=["dt.host.cpu.usage"],
        keywords=["cpu", "processador", "host", "saturacao", "capacidade"],
        priority=90, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="hosts.memory_trend",
        domain="hosts", signal="saturation",
        title="Memoria por host (media)",
        question="Como esta o consumo de memoria dos hosts?",
        query=("timeseries memoria = avg(dt.host.memory.usage), by:{dt.smartscape.host}\n"
               "| fieldsAdd host = getNodeName(dt.smartscape.host)"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Infraestrutura",
        metrics=["dt.host.memory.usage"],
        keywords=["memoria", "memory", "ram", "host", "saturacao"],
        priority=85, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="hosts.top_cpu",
        domain="hosts", signal="saturation",
        title="Top 10 hosts por CPU",
        question="Quais hosts estao com maior consumo de CPU?",
        query=("timeseries cpu = avg(dt.host.cpu.usage), by:{dt.smartscape.host}\n"
               "| fieldsAdd host = getNodeName(dt.smartscape.host), cpu_media = arrayAvg(cpu)\n"
               "| fields host, cpu_media\n"
               "| sort cpu_media desc\n"
               "| limit 10"),
        visualization="categoricalBarChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Infraestrutura",
        metrics=["dt.host.cpu.usage"],
        keywords=["cpu", "top", "ranking", "host", "gargalo"],
        priority=75, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="hosts.disk_pressure",
        domain="hosts", signal="saturation",
        title="Hosts com maior uso de disco",
        question="Algum host esta perto de encher o disco?",
        query=("timeseries disco = avg(dt.host.disk.used.percent), by:{dt.smartscape.host}\n"
               "| fieldsAdd host = getNodeName(dt.smartscape.host), uso_disco = arrayAvg(disco)\n"
               "| fields host, uso_disco\n"
               "| sort uso_disco desc\n"
               "| limit 15"),
        visualization="table", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Infraestrutura",
        metrics=["dt.host.disk.used.percent"],
        keywords=["disco", "disk", "storage", "espaco", "filesystem"],
        priority=65,
    ),
    Blueprint(
        bp_id="hosts.saturation_table",
        domain="hosts", signal="saturation",
        title="Saturacao por host (CPU / memoria / disco)",
        question="Quais hosts estao saturados agora?",
        query=("timeseries {\n"
               "  cpu = avg(dt.host.cpu.usage),\n"
               "  memoria = avg(dt.host.memory.usage),\n"
               "  disco = avg(dt.host.disk.used.percent)\n"
               "}, by:{dt.smartscape.host}\n"
               "| fieldsAdd host = getNodeName(dt.smartscape.host),\n"
               "    cpu_media = arrayAvg(cpu), memoria_media = arrayAvg(memoria), disco_medio = arrayAvg(disco)\n"
               "| fields host, cpu_media, memoria_media, disco_medio\n"
               "| sort cpu_media desc\n"
               "| limit 25"),
        visualization="table", source_kind="timeseries", filter_object="metrics",
        width=24, height=9, section="Infraestrutura",
        metrics=["dt.host.cpu.usage", "dt.host.memory.usage", "dt.host.disk.used.percent"],
        keywords=["saturacao", "capacidade", "host", "recursos", "cpu", "memoria", "disco"],
        priority=60,
    ),
    Blueprint(
        bp_id="hosts.by_os",
        domain="hosts", signal="inventory",
        title="Hosts por sistema operacional",
        question="Como o parque esta distribuido por SO e nuvem?",
        query=('smartscapeNodes "HOST"\n'
               "| fieldsAdd os.type, cloud.provider\n"
               "| summarize hosts = count(), by:{os.type}\n"
               "| sort hosts desc"),
        visualization="donutChart", source_kind="smartscape", filter_object="smartscape",
        width=8, height=6, section="Infraestrutura",
        keywords=["sistema operacional", "so", "inventario", "parque", "windows", "linux"],
        priority=40, visualization_settings=DONUT,
    ),

    # ============================================================ KUBERNETES
    Blueprint(
        bp_id="k8s.clusters",
        domain="kubernetes", signal="inventory",
        title="Clusters Kubernetes",
        question="Quais clusters estao monitorados e em que versao?",
        query=("smartscapeNodes K8S_CLUSTER\n"
               "| fields k8s.cluster.name, k8s.cluster.version, k8s.cluster.distribution\n"
               "| sort k8s.cluster.name asc"),
        visualization="table", source_kind="smartscape", filter_object="smartscape",
        width=12, height=6, section="Kubernetes",
        keywords=["kubernetes", "k8s", "cluster", "clusters", "openshift"],
        priority=60,
    ),
    Blueprint(
        bp_id="k8s.pods_trend",
        domain="kubernetes", signal="traffic",
        title="Pods em execucao por cluster",
        question="Como varia a quantidade de pods no periodo?",
        query="timeseries pods = avg(dt.kubernetes.pods), by:{k8s.cluster.name}",
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Kubernetes",
        metrics=["dt.kubernetes.pods"],
        keywords=["pod", "pods", "kubernetes", "k8s", "capacidade"],
        priority=80, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="k8s.cpu_by_namespace",
        domain="kubernetes", signal="saturation",
        title="CPU por namespace",
        question="Quais namespaces consomem mais CPU?",
        query=("timeseries cpu = sum(dt.kubernetes.container.cpu_usage), by:{k8s.namespace.name}"),
        visualization="areaChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Kubernetes",
        metrics=["dt.kubernetes.container.cpu_usage"],
        keywords=["cpu", "namespace", "kubernetes", "k8s", "consumo"],
        priority=85, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="k8s.memory_by_namespace",
        domain="kubernetes", signal="saturation",
        title="Memoria (working set) por namespace",
        question="Quais namespaces consomem mais memoria?",
        query=("timeseries memoria = sum(dt.kubernetes.container.memory_working_set), "
               "by:{k8s.namespace.name}"),
        visualization="areaChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Kubernetes",
        metrics=["dt.kubernetes.container.memory_working_set"],
        keywords=["memoria", "memory", "namespace", "kubernetes", "k8s"],
        priority=80, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="k8s.restarts",
        domain="kubernetes", signal="errors",
        title="Pods com mais reinicios",
        question="Quais pods estao reiniciando com frequencia?",
        query=("timeseries reinicios = sum(dt.kubernetes.container.restarts),\n"
               "  by:{k8s.pod.name, k8s.namespace.name, k8s.cluster.name}\n"
               "| fieldsAdd total_reinicios = arraySum(reinicios)\n"
               "| filter total_reinicios > 0\n"
               "| fields k8s.cluster.name, k8s.namespace.name, k8s.pod.name, total_reinicios\n"
               "| sort total_reinicios desc\n"
               "| limit 20"),
        visualization="table", source_kind="timeseries", filter_object="metrics",
        width=12, height=8, section="Kubernetes",
        metrics=["dt.kubernetes.container.restarts"],
        keywords=["restart", "reinicio", "crashloop", "pod", "kubernetes", "instabilidade"],
        priority=88,
    ),
    Blueprint(
        bp_id="k8s.oom",
        domain="kubernetes", signal="errors",
        title="OOM kills por pod",
        question="Algum container esta sendo morto por falta de memoria?",
        query=("timeseries oom = sum(dt.kubernetes.container.oom_kills),\n"
               "  by:{k8s.pod.name, k8s.namespace.name, k8s.cluster.name}\n"
               "| fieldsAdd total_oom = arraySum(oom)\n"
               "| filter total_oom > 0\n"
               "| fields k8s.cluster.name, k8s.namespace.name, k8s.pod.name, total_oom\n"
               "| sort total_oom desc\n"
               "| limit 20"),
        visualization="table", source_kind="timeseries", filter_object="metrics",
        width=12, height=8, section="Kubernetes",
        metrics=["dt.kubernetes.container.oom_kills"],
        keywords=["oom", "out of memory", "memoria", "kill", "kubernetes"],
        priority=70,
    ),
    Blueprint(
        bp_id="k8s.pods_not_running",
        domain="kubernetes", signal="errors",
        title="Pods fora do estado Running",
        question="Existem pods pendentes, com erro ou em CrashLoop?",
        query=("smartscapeNodes K8S_POD\n"
               '| parse k8s.object, "JSON:config"\n'
               "| fieldsAdd fase = config[status][phase]\n"
               '| filter fase != "Running"\n'
               "| fields k8s.cluster.name, k8s.namespace.name, k8s.pod.name, fase\n"
               "| limit 50"),
        visualization="table", source_kind="smartscape", filter_object="smartscape",
        width=12, height=8, section="Kubernetes",
        keywords=["pending", "crashloop", "erro", "pod", "kubernetes", "falha"],
        priority=75,
    ),
    Blueprint(
        bp_id="k8s.node_capacity",
        domain="kubernetes", signal="saturation",
        title="Capacidade de pods por node",
        question="Algum node esta perto do limite de pods?",
        query=("timeseries {\n"
               "  pods = avg(dt.kubernetes.pods),\n"
               "  alocaveis = avg(dt.kubernetes.node.pods_allocatable)\n"
               "}, by:{k8s.node.name, k8s.cluster.name}\n"
               "| fieldsAdd ocupacao_pct = (arrayAvg(pods) / arrayAvg(alocaveis)) * 100\n"
               "| fields k8s.cluster.name, k8s.node.name, ocupacao_pct\n"
               "| sort ocupacao_pct desc\n"
               "| limit 20"),
        visualization="table", source_kind="timeseries", filter_object="metrics",
        width=12, height=8, section="Kubernetes",
        metrics=["dt.kubernetes.pods", "dt.kubernetes.node.pods_allocatable"],
        keywords=["node", "capacidade", "kubernetes", "limite", "scheduling"],
        priority=55,
    ),
    Blueprint(
        bp_id="k8s.errors_by_namespace",
        domain="kubernetes", signal="errors",
        title="Logs de erro por namespace",
        question="Onde estao concentrados os erros no cluster?",
        query=("fetch logs\n"
               '| filter in(status, {"ERROR", "FATAL"})\n'
               "| filter isNotNull(k8s.namespace.name)\n"
               "| summarize erros = count(), by:{k8s.namespace.name}\n"
               "| sort erros desc\n"
               "| limit 15"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="logs",
        width=12, height=7, section="Kubernetes",
        requires=["logs"],
        keywords=["erro", "log", "namespace", "kubernetes"],
        priority=72, visualization_settings=BARS,
    ),

    # ============================================================== SERVICES
    Blueprint(
        bp_id="services.request_rate",
        domain="services", signal="traffic",
        title="Requisicoes por servico",
        question="Qual o volume de requisicoes por servico?",
        query="timeseries requisicoes = sum(dt.service.request.count), by:{dt.service.name}",
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Servicos",
        metrics=["dt.service.request.count"],
        keywords=["requisicao", "requisicoes", "throughput", "trafego", "servico", "carga", "volume"],
        priority=90, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="services.response_time",
        domain="services", signal="latency",
        title="Tempo de resposta p90 por servico",
        question="Os servicos estao dentro do tempo de resposta esperado?",
        query=("timeseries p90 = percentile(dt.service.request.response_time, 90), "
               "by:{dt.service.name}"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Servicos",
        metrics=["dt.service.request.response_time"],
        keywords=["latencia", "tempo de resposta", "performance", "lentidao", "p90", "percentil"],
        priority=92, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="services.error_rate_trend",
        domain="services", signal="errors",
        title="Taxa de erro por servico",
        question="Quais servicos estao falhando e quando?",
        query=("timeseries {\n"
               "  total = sum(dt.service.request.count),\n"
               "  falhas = sum(dt.service.request.failure_count)\n"
               "}, by:{dt.service.name}\n"
               "| fieldsAdd taxa_erro_pct = (falhas[] * 100.0) / total[]"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Servicos",
        metrics=["dt.service.request.count", "dt.service.request.failure_count"],
        keywords=["erro", "erros", "falha", "falhas", "taxa de erro", "indisponibilidade"],
        priority=95, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="services.golden_table",
        domain="services", signal="latency",
        title="Sinais de ouro por servico",
        question="Qual a visao consolidada de trafego, erros e latencia por servico?",
        query=("timeseries {\n"
               "  p50 = percentile(dt.service.request.response_time, 50),\n"
               "  p90 = percentile(dt.service.request.response_time, 90),\n"
               "  p99 = percentile(dt.service.request.response_time, 99),\n"
               "  total = sum(dt.service.request.count),\n"
               "  falhas = sum(dt.service.request.failure_count)\n"
               "}, by:{dt.service.name}\n"
               "| fieldsAdd\n"
               "    requisicoes = arraySum(total),\n"
               "    erros = arraySum(falhas),\n"
               "    p50_ms = arrayAvg(p50) / 1000,\n"
               "    p90_ms = arrayAvg(p90) / 1000,\n"
               "    p99_ms = arrayAvg(p99) / 1000\n"
               "| fieldsAdd taxa_erro_pct = if(requisicoes > 0, (erros * 100.0) / requisicoes, else: 0.0)\n"
               "| fields dt.service.name, requisicoes, erros, taxa_erro_pct, p50_ms, p90_ms, p99_ms\n"
               "| sort taxa_erro_pct desc\n"
               "| limit 25"),
        visualization="table", source_kind="timeseries", filter_object="metrics",
        width=24, height=10, section="Servicos",
        metrics=["dt.service.request.response_time", "dt.service.request.count",
                 "dt.service.request.failure_count"],
        keywords=["servico", "servicos", "visao geral", "sinais de ouro", "golden signals",
                  "consolidado", "resumo"],
        priority=86,
    ),
    Blueprint(
        bp_id="services.top_slowest",
        domain="services", signal="latency",
        title="Top 10 servicos mais lentos (p90)",
        question="Quais servicos mais degradam a experiencia?",
        query=("timeseries p90 = percentile(dt.service.request.response_time, 90), "
               "by:{dt.service.name}\n"
               "| fieldsAdd p90_ms = arrayAvg(p90) / 1000\n"
               "| fields dt.service.name, p90_ms\n"
               "| sort p90_ms desc\n"
               "| limit 10"),
        visualization="categoricalBarChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Servicos",
        metrics=["dt.service.request.response_time"],
        keywords=["lento", "lentidao", "latencia", "top", "ranking", "gargalo"],
        priority=78, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="services.requests_kpi",
        domain="services", signal="traffic",
        title="Total de requisicoes",
        question="Qual o volume total de requisicoes no periodo?",
        query=("timeseries total = sum(dt.service.request.count)\n"
               "| fieldsAdd requisicoes = arraySum(total)\n"
               "| fields requisicoes"),
        visualization="singleValue", source_kind="timeseries", filter_object="metrics",
        width=6, height=4, section="Resumo executivo",
        metrics=["dt.service.request.count"],
        keywords=["total", "kpi", "requisicoes", "volume", "trafego"],
        priority=82, visualization_settings=_single("requisicoes", "Requisicoes"),
    ),
    Blueprint(
        bp_id="services.error_rate_kpi",
        domain="services", signal="errors",
        title="Taxa de erro global",
        question="Qual a taxa de erro consolidada do ambiente?",
        query=("timeseries {\n"
               "  total = sum(dt.service.request.count),\n"
               "  falhas = sum(dt.service.request.failure_count)\n"
               "}\n"
               "| fieldsAdd requisicoes = arraySum(total), erros = arraySum(falhas)\n"
               "| fieldsAdd taxa_erro_pct = if(requisicoes > 0, (erros * 100.0) / requisicoes, else: 0.0)\n"
               "| fields taxa_erro_pct"),
        visualization="singleValue", source_kind="timeseries", filter_object="metrics",
        width=6, height=4, section="Resumo executivo",
        metrics=["dt.service.request.count", "dt.service.request.failure_count"],
        keywords=["taxa de erro", "erro", "kpi", "qualidade", "disponibilidade"],
        priority=94,
        visualization_settings=_single("taxa_erro_pct", "Taxa de erro (%)"),
    ),
    Blueprint(
        bp_id="services.slow_endpoints",
        domain="spans", signal="latency",
        title="Operacoes mais lentas (spans)",
        question="Quais operacoes/endpoints estao mais lentos?",
        query=("fetch spans\n"
               "| filter request.is_root_span == true\n"
               "| summarize chamadas = count(), p90 = percentile(duration, 90), "
               "by:{dt.service.name, span.name}\n"
               "| fields dt.service.name, span.name, chamadas, p90\n"
               "| sort p90 desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="spans",
        width=12, height=8, section="Servicos",
        requires=["spans"],
        keywords=["endpoint", "operacao", "span", "trace", "lento", "latencia", "transacao"],
        priority=70,
    ),
    Blueprint(
        bp_id="services.failed_spans",
        domain="spans", signal="errors",
        title="Operacoes com mais falhas (spans)",
        question="Quais operacoes concentram as falhas?",
        query=("fetch spans\n"
               "| filter request.is_failed == true\n"
               "| summarize falhas = count(), by:{dt.service.name, span.name}\n"
               "| sort falhas desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="spans",
        width=12, height=8, section="Servicos",
        requires=["spans"],
        keywords=["falha", "erro", "span", "trace", "excecao", "endpoint"],
        priority=68,
    ),

    # ================================================================== LOGS
    Blueprint(
        bp_id="logs.volume_trend",
        domain="logs", signal="traffic",
        title="Volume de logs por severidade",
        question="Como evolui o volume de logs no periodo?",
        query=("fetch logs\n"
               "| makeTimeseries registros = count(), by:{status}"),
        visualization="areaChart", source_kind="fetch", filter_object="logs",
        width=12, height=7, section="Logs",
        requires=["logs"],
        keywords=["log", "logs", "volume", "ingestao", "severidade"],
        priority=75, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="logs.error_trend",
        domain="logs", signal="errors",
        title="Erros em log ao longo do tempo",
        question="Quando os erros aumentaram?",
        query=("fetch logs\n"
               '| filter in(status, {"ERROR", "FATAL"})\n'
               "| makeTimeseries erros = count()"),
        visualization="lineChart", source_kind="fetch", filter_object="logs",
        width=12, height=7, section="Logs",
        requires=["logs"],
        keywords=["erro", "erros", "log", "logs", "falha", "excecao"],
        priority=88, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="logs.severity_donut",
        domain="logs", signal="errors",
        title="Distribuicao por severidade",
        question="Como os logs se distribuem entre as severidades?",
        query=("fetch logs\n"
               "| summarize registros = count(), by:{status}\n"
               "| sort registros desc"),
        visualization="donutChart", source_kind="fetch", filter_object="logs",
        width=8, height=6, section="Logs",
        requires=["logs"],
        keywords=["severidade", "log", "logs", "distribuicao", "warn", "error"],
        priority=60, visualization_settings=DONUT,
    ),
    Blueprint(
        bp_id="logs.top_errors",
        domain="logs", signal="errors",
        title="Principais mensagens de erro",
        question="Quais mensagens de erro mais se repetem?",
        query=("fetch logs\n"
               '| filter in(status, {"ERROR", "FATAL"})\n'
               "| summarize ocorrencias = count(), by:{content}\n"
               "| sort ocorrencias desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="logs",
        width=24, height=9, section="Logs",
        requires=["logs"],
        keywords=["mensagem", "erro", "log", "top", "recorrente", "causa"],
        priority=84,
    ),
    Blueprint(
        bp_id="logs.by_source",
        domain="logs", signal="errors",
        title="Erros por origem (process group)",
        question="Quais componentes geram mais erros?",
        query=("fetch logs\n"
               '| filter in(status, {"ERROR", "FATAL"})\n'
               "| summarize erros = count(), by:{dt.process_group.detected_name}\n"
               "| filter isNotNull(dt.process_group.detected_name)\n"
               "| sort erros desc\n"
               "| limit 15"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="logs",
        width=12, height=7, section="Logs",
        requires=["logs"],
        keywords=["origem", "componente", "processo", "erro", "log"],
        priority=70, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="logs.error_kpi",
        domain="logs", signal="errors",
        title="Erros em log no periodo",
        question="Quantos erros de log ocorreram?",
        query=("fetch logs\n"
               '| filter in(status, {"ERROR", "FATAL"})\n'
               "| summarize erros = count()"),
        visualization="singleValue", source_kind="fetch", filter_object="logs",
        width=6, height=4, section="Resumo executivo",
        requires=["logs"],
        keywords=["erro", "log", "kpi", "total"],
        priority=76, visualization_settings=_single("erros", "Erros em log"),
    ),

    # ============================================================== PROBLEMS
    Blueprint(
        bp_id="problems.active_kpi",
        domain="problems", signal="errors",
        title="Problemas ativos",
        question="Quantos problemas o Davis tem abertos agora?",
        query=("fetch dt.davis.problems\n"
               '| filter not(dt.davis.is_duplicate) and event.status == "ACTIVE"\n'
               "| summarize problemas = count()"),
        visualization="singleValue", source_kind="fetch", filter_object="dt.davis.problems",
        width=6, height=4, section="Resumo executivo",
        requires=["dt.davis.problems"],
        keywords=["problema", "problemas", "davis", "incidente", "alerta", "aberto"],
        priority=96, visualization_settings=_single("problemas", "Problemas ativos"),
    ),
    Blueprint(
        bp_id="problems.timeline",
        domain="problems", signal="errors",
        title="Problemas ao longo do tempo",
        question="Como os problemas se distribuem no periodo?",
        query=("fetch dt.davis.problems\n"
               "| filter not(dt.davis.is_duplicate)\n"
               "| summarize problemas = count(), by:{intervalo = bin(event.start, 1h), event.category}\n"
               "| sort intervalo asc"),
        visualization="lineChart", source_kind="fetch", filter_object="dt.davis.problems",
        width=12, height=7, section="Problemas",
        requires=["dt.davis.problems"],
        keywords=["problema", "historico", "tendencia", "incidente", "davis"],
        priority=80, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="problems.by_category",
        domain="problems", signal="errors",
        title="Problemas por categoria",
        question="Que tipos de problema predominam?",
        query=("fetch dt.davis.problems\n"
               '| filter not(dt.davis.is_duplicate) and event.status == "ACTIVE"\n'
               "| summarize problemas = count(), by:{event.category}\n"
               "| sort problemas desc"),
        visualization="donutChart", source_kind="fetch", filter_object="dt.davis.problems",
        width=8, height=6, section="Problemas",
        requires=["dt.davis.problems"],
        keywords=["categoria", "problema", "tipo", "davis"],
        priority=65, visualization_settings=DONUT,
    ),
    Blueprint(
        bp_id="problems.active_table",
        domain="problems", signal="errors",
        title="Problemas ativos (detalhe)",
        question="Quais problemas estao abertos e quem eles afetam?",
        query=("fetch dt.davis.problems\n"
               '| filter not(dt.davis.is_duplicate) and event.status == "ACTIVE"\n'
               "| fields event.start, display_id, event.name, event.category, "
               "dt.davis.affected_users_count\n"
               "| sort event.start desc\n"
               "| limit 25"),
        visualization="table", source_kind="fetch", filter_object="dt.davis.problems",
        width=24, height=9, section="Problemas",
        requires=["dt.davis.problems"],
        keywords=["problema", "detalhe", "aberto", "incidente", "impacto"],
        priority=90,
    ),
    Blueprint(
        bp_id="problems.top_impact",
        domain="problems", signal="errors",
        title="Problemas com maior impacto em usuarios",
        question="Quais problemas afetam mais usuarios?",
        query=("fetch dt.davis.problems\n"
               "| filter not(dt.davis.is_duplicate)\n"
               "| filter dt.davis.affected_users_count > 0\n"
               "| fields display_id, event.name, dt.davis.affected_users_count, event.status\n"
               "| sort dt.davis.affected_users_count desc\n"
               "| limit 15"),
        visualization="table", source_kind="fetch", filter_object="dt.davis.problems",
        width=12, height=8, section="Problemas",
        requires=["dt.davis.problems"],
        keywords=["impacto", "usuario", "usuarios", "problema", "negocio"],
        priority=72,
    ),

    # =================================================================== RUM
    Blueprint(
        bp_id="rum.active_users",
        domain="rum", signal="traffic",
        title="Usuarios ativos por aplicacao",
        question="Quantos usuarios estao usando as aplicacoes?",
        query=("timeseries usuarios = countDistinct(dt.frontend.user.active.estimated_count),\n"
               "  by:{frontend.name}"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Experiencia do usuario",
        metrics=["dt.frontend.user.active.estimated_count"],
        keywords=["usuario", "usuarios", "rum", "experiencia", "sessao", "frontend", "aplicacao"],
        priority=85, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="rum.sessions",
        domain="rum", signal="traffic",
        title="Sessoes ativas por aplicacao",
        question="Como evolui o numero de sessoes?",
        query=("timeseries sessoes = countDistinct(dt.frontend.session.active.estimated_count),\n"
               "  by:{frontend.name}"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Experiencia do usuario",
        metrics=["dt.frontend.session.active.estimated_count"],
        keywords=["sessao", "sessoes", "rum", "usuario", "frontend"],
        priority=78, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="rum.errors",
        domain="rum", signal="errors",
        title="Erros de frontend",
        question="Os usuarios estao encontrando erros na interface?",
        query="timeseries erros = sum(dt.frontend.error.count), by:{frontend.name}",
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Experiencia do usuario",
        metrics=["dt.frontend.error.count"],
        keywords=["erro", "javascript", "frontend", "rum", "usuario"],
        priority=82, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="rum.web_vitals",
        domain="rum", signal="latency",
        title="Core Web Vitals (p75) por aplicacao",
        question="A experiencia web esta dentro dos Core Web Vitals?",
        query=("timeseries {\n"
               "  lcp_p75 = percentile(dt.frontend.web.page.largest_contentful_paint, 75, scalar: true),\n"
               "  inp_p75 = percentile(dt.frontend.web.page.interaction_to_next_paint, 75, scalar: true),\n"
               "  cls_p75 = percentile(dt.frontend.web.page.cumulative_layout_shift, 75, scalar: true)\n"
               "}, by:{frontend.name}\n"
               "| sort lcp_p75 desc"),
        visualization="table", source_kind="timeseries", filter_object="metrics",
        width=12, height=8, section="Experiencia do usuario",
        metrics=["dt.frontend.web.page.largest_contentful_paint",
                 "dt.frontend.web.page.interaction_to_next_paint",
                 "dt.frontend.web.page.cumulative_layout_shift"],
        keywords=["web vitals", "lcp", "inp", "cls", "performance", "experiencia", "pagina"],
        priority=80,
    ),
    Blueprint(
        bp_id="rum.user_actions",
        domain="rum", signal="latency",
        title="Duracao das acoes de usuario",
        question="As acoes do usuario estao rapidas?",
        query=("timeseries duracao = avg(dt.frontend.user_action.duration), by:{frontend.name}"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Experiencia do usuario",
        metrics=["dt.frontend.user_action.duration"],
        keywords=["acao", "user action", "clique", "duracao", "rum"],
        priority=62, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="rum.geo",
        domain="rum", signal="traffic",
        title="Usuarios por pais",
        question="De onde vem o trafego dos usuarios?",
        query=("timeseries usuarios = countDistinct(dt.frontend.user.active.estimated_count, "
               "scalar: true),\n"
               "  by:{geo.country.iso_code}\n"
               "| filter isNotNull(geo.country.iso_code)\n"
               "| sort usuarios desc"),
        visualization="choroplethMap", source_kind="timeseries", filter_object="metrics",
        width=12, height=8, section="Experiencia do usuario",
        metrics=["dt.frontend.user.active.estimated_count"],
        keywords=["geografia", "pais", "regiao", "mapa", "usuario"],
        priority=45,
    ),

    # ============================================================== DATABASE
    Blueprint(
        bp_id="db.calls",
        domain="database", signal="traffic",
        title="Chamadas de banco por tecnologia",
        question="Qual o volume de acesso a bancos de dados?",
        query=("fetch spans\n"
               "| filter isNotNull(db.system)\n"
               "| summarize chamadas = count(), by:{db.system}\n"
               "| sort chamadas desc"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="spans",
        width=12, height=7, section="Banco de dados",
        requires=["spans"],
        keywords=["banco", "database", "sql", "db", "query", "consulta"],
        priority=60, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="db.slow_statements",
        domain="database", signal="latency",
        title="Comandos de banco mais lentos",
        question="Quais consultas estao degradando a aplicacao?",
        query=("fetch spans\n"
               "| filter isNotNull(db.system)\n"
               "| summarize chamadas = count(), p90 = percentile(duration, 90), "
               "by:{dt.service.name, db.system}\n"
               "| sort p90 desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="spans",
        width=12, height=8, section="Banco de dados",
        requires=["spans"],
        keywords=["lento", "consulta", "sql", "banco", "database", "latencia"],
        priority=58,
    ),

    # ============================================================== SECURITY
    Blueprint(
        bp_id="security.vulns_by_risk",
        domain="security", signal="errors",
        title="Vulnerabilidades abertas por risco",
        question="Qual a exposicao atual por nivel de risco?",
        query=("fetch security.events\n"
               '| filter event.type == "VULNERABILITY_STATE_REPORT_EVENT"\n'
               '| filter vulnerability.resolution.status == "OPEN"\n'
               "| dedup {vulnerability.display_id}, sort:{timestamp desc}\n"
               "| summarize vulnerabilidades = count(), by:{vulnerability.risk.level}\n"
               "| sort vulnerabilidades desc"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="security.events",
        width=12, height=7, section="Seguranca",
        requires=["security.events"],
        keywords=["vulnerabilidade", "seguranca", "risco", "cve", "exposicao"],
        priority=80, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="security.top_vulns",
        domain="security", signal="errors",
        title="Principais vulnerabilidades abertas",
        question="Quais vulnerabilidades priorizar?",
        query=("fetch security.events\n"
               '| filter event.type == "VULNERABILITY_STATE_REPORT_EVENT"\n'
               '| filter vulnerability.resolution.status == "OPEN"\n'
               "| dedup {vulnerability.display_id}, sort:{timestamp desc}\n"
               "| fields vulnerability.display_id, vulnerability.title, vulnerability.risk.level, "
               "vulnerability.risk.score\n"
               "| sort vulnerability.risk.score desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="security.events",
        width=24, height=9, section="Seguranca",
        requires=["security.events"],
        keywords=["vulnerabilidade", "cve", "prioridade", "seguranca", "risco"],
        priority=75,
    ),

    # ============================================================= BIZEVENTS
    Blueprint(
        bp_id="biz.volume",
        domain="bizevents", signal="traffic",
        title="Eventos de negocio por tipo",
        question="Qual o volume dos eventos de negocio?",
        query=("fetch bizevents\n"
               "| summarize eventos = count(), by:{event.type}\n"
               "| sort eventos desc\n"
               "| limit 20"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="bizevents",
        width=12, height=7, section="Negocio",
        requires=["bizevents"],
        keywords=["negocio", "bizevent", "business", "transacao", "pedido", "venda", "conversao"],
        priority=70, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="biz.trend",
        domain="bizevents", signal="traffic",
        title="Eventos de negocio ao longo do tempo",
        question="Como o volume de negocio evolui no periodo?",
        query=("fetch bizevents\n"
               "| makeTimeseries eventos = count(), by:{event.type}"),
        visualization="areaChart", source_kind="fetch", filter_object="bizevents",
        width=12, height=7, section="Negocio",
        requires=["bizevents"],
        keywords=["negocio", "tendencia", "bizevent", "volume", "vendas"],
        priority=68, visualization_settings=LINE,
    ),

    # =================================================================== DPS
    Blueprint(
        bp_id="dps.by_capability",
        domain="dps", signal="cost",
        title="Consumo DPS por capacidade (eventos)",
        question="Quais capacidades da plataforma estao sendo consumidas?",
        query=("fetch dt.system.events\n"
               '| filter event.kind == "BILLING_USAGE_EVENT"\n'
               "| summarize eventos = count(), by:{event.type}\n"
               "| sort eventos desc\n"
               "| limit 20"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="dt.system.events",
        width=12, height=7, section="Consumo da plataforma (DPS)",
        requires=["dt.system.events"], dps_only=True,
        keywords=["dps", "consumo", "custo", "billing", "licenca", "plataforma", "finops"],
        priority=85, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="dps.ingest_gib",
        domain="dps", signal="cost",
        title="Volume faturado (GiB) por capacidade",
        question="Quanto volume esta sendo faturado por capacidade?",
        query=("fetch dt.system.events\n"
               '| filter event.kind == "BILLING_USAGE_EVENT"\n'
               "| filter isNotNull(billed_bytes)\n"
               "| dedup {event.id, event.type}\n"
               "| summarize gib = sum(toDouble(billed_bytes) / 1073741824), by:{event.type}\n"
               "| sort gib desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="dt.system.events",
        width=12, height=8, section="Consumo da plataforma (DPS)",
        requires=["dt.system.events"], dps_only=True,
        keywords=["ingestao", "gib", "volume", "custo", "dps", "faturado", "bytes"],
        priority=82,
    ),
    Blueprint(
        bp_id="dps.query_cost",
        domain="dps", signal="cost",
        title="Custo de consulta por origem",
        question="Quem esta varrendo mais dados no Grail?",
        query=("fetch dt.system.events\n"
               '| filter event.kind == "BILLING_USAGE_EVENT"\n'
               '| filter in(event.type, "Log Management & Analytics - Query", "Events - Query", '
               '"Traces - Query", "Files - Query")\n'
               "| dedup {event.id, event.type}\n"
               "| fieldsAdd origem = coalesce(client.source, client.application_context, "
               'client.workflow_context, "desconhecido")\n'
               "| summarize gib = sum(toDouble(billed_bytes) / 1073741824), by:{origem}\n"
               "| sort gib desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="dt.system.events",
        width=12, height=8, section="Consumo da plataforma (DPS)",
        requires=["dt.system.events"], dps_only=True,
        keywords=["query", "consulta", "custo", "scan", "grail", "dps", "origem"],
        priority=78,
    ),
    Blueprint(
        bp_id="dps.daily_trend",
        domain="dps", signal="cost",
        title="Tendencia diaria de consumo",
        question="O consumo esta crescendo?",
        query=("fetch dt.system.events\n"
               '| filter event.kind == "BILLING_USAGE_EVENT"\n'
               "| filter isNotNull(billed_bytes)\n"
               "| dedup {event.id, event.type}\n"
               "| summarize gib = sum(toDouble(billed_bytes) / 1073741824), "
               "by:{dia = bin(timestamp, 1d)}\n"
               "| sort dia asc"),
        visualization="barChart", source_kind="fetch", filter_object="dt.system.events",
        width=12, height=7, section="Consumo da plataforma (DPS)",
        requires=["dt.system.events"], dps_only=True,
        keywords=["tendencia", "consumo", "diario", "custo", "dps", "crescimento"],
        priority=74, visualization_settings=LINE,
    ),
    # ------------------------------------------------- complementos por dominio
    Blueprint(
        bp_id="db.errors",
        domain="database", signal="errors",
        title="Falhas de acesso a banco",
        question="As chamadas a banco estao falhando?",
        query=("fetch spans\n"
               "| filter isNotNull(db.system) and request.is_failed == true\n"
               "| summarize falhas = count(), by:{dt.service.name, db.system, db.namespace}\n"
               "| sort falhas desc\n"
               "| limit 20"),
        visualization="table", source_kind="fetch", filter_object="spans",
        width=12, height=8, section="Banco de dados",
        requires=["spans"],
        keywords=["banco", "database", "erro", "falha", "sql", "conexao"],
        priority=56,
    ),
    Blueprint(
        bp_id="db.calls_trend",
        domain="database", signal="traffic",
        title="Chamadas de banco ao longo do tempo",
        question="Como varia o acesso ao banco no periodo?",
        query=("fetch spans\n"
               "| filter isNotNull(db.system)\n"
               "| makeTimeseries chamadas = count(), by:{db.system}"),
        visualization="lineChart", source_kind="fetch", filter_object="spans",
        width=12, height=7, section="Banco de dados",
        requires=["spans"],
        keywords=["banco", "database", "tendencia", "volume", "sql"],
        priority=54, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="messaging.throughput",
        domain="services", signal="traffic",
        title="Mensageria: publicacao, consumo e falhas",
        question="As filas estao processando sem acumulo ou falha?",
        query=("timeseries {\n"
               "  publicadas = sum(dt.service.messaging.publish.count),\n"
               "  recebidas = sum(dt.service.messaging.receive.count),\n"
               "  processadas = sum(dt.service.messaging.process.count),\n"
               "  falhas = sum(dt.service.messaging.process.failure_count)\n"
               "}, by:{dt.service.name}"),
        visualization="lineChart", source_kind="timeseries", filter_object="metrics",
        width=12, height=7, section="Servicos",
        metrics=["dt.service.messaging.publish.count", "dt.service.messaging.receive.count",
                 "dt.service.messaging.process.count",
                 "dt.service.messaging.process.failure_count"],
        keywords=["fila", "filas", "kafka", "mensageria", "messaging", "topico", "rabbitmq",
                  "sqs", "consumo de fila"],
        priority=58, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="security.vulns_trend",
        domain="security", signal="errors",
        title="Vulnerabilidades detectadas ao longo do tempo",
        question="A exposicao esta crescendo ou sendo tratada?",
        query=("fetch security.events\n"
               '| filter event.type == "VULNERABILITY_STATE_REPORT_EVENT"\n'
               "| summarize vulnerabilidades = countDistinct(vulnerability.display_id), "
               "by:{intervalo = bin(timestamp, 1h)}\n"
               "| sort intervalo asc"),
        visualization="lineChart", source_kind="fetch", filter_object="security.events",
        width=12, height=7, section="Seguranca",
        requires=["security.events"],
        keywords=["vulnerabilidade", "tendencia", "seguranca", "exposicao", "historico"],
        priority=66, visualization_settings=LINE,
    ),
    Blueprint(
        bp_id="security.by_stack",
        domain="security", signal="errors",
        title="Vulnerabilidades abertas por stack",
        question="Quais tecnologias concentram a exposicao?",
        query=("fetch security.events\n"
               '| filter event.type == "VULNERABILITY_STATE_REPORT_EVENT"\n'
               '| filter vulnerability.resolution.status == "OPEN"\n'
               "| dedup {vulnerability.display_id}, sort:{timestamp desc}\n"
               "| summarize vulnerabilidades = count(), by:{vulnerability.stack}\n"
               "| sort vulnerabilidades desc"),
        visualization="donutChart", source_kind="fetch", filter_object="security.events",
        width=8, height=6, section="Seguranca",
        requires=["security.events"],
        keywords=["stack", "tecnologia", "vulnerabilidade", "seguranca", "java", "node"],
        priority=60, visualization_settings=DONUT,
    ),
    Blueprint(
        bp_id="biz.recent",
        domain="bizevents", signal="traffic",
        title="Eventos de negocio recentes",
        question="O que esta chegando de eventos de negocio agora?",
        query=("fetch bizevents\n"
               "| fields timestamp, event.type, event.provider\n"
               "| sort timestamp desc\n"
               "| limit 50"),
        visualization="table", source_kind="fetch", filter_object="bizevents",
        width=12, height=8, section="Negocio",
        requires=["bizevents"],
        keywords=["negocio", "evento", "detalhe", "recente", "transacao"],
        priority=60,
    ),
    Blueprint(
        bp_id="biz.by_provider",
        domain="bizevents", signal="traffic",
        title="Eventos de negocio por origem",
        question="Quais sistemas geram os eventos de negocio?",
        query=("fetch bizevents\n"
               "| summarize eventos = count(), by:{event.provider}\n"
               "| sort eventos desc\n"
               "| limit 15"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="bizevents",
        width=12, height=7, section="Negocio",
        requires=["bizevents"],
        keywords=["origem", "provider", "negocio", "sistema", "canal"],
        priority=58, visualization_settings=BARS,
    ),
    Blueprint(
        bp_id="logs.by_bucket",
        domain="logs", signal="cost",
        title="Volume de logs por bucket",
        question="Quais buckets concentram o volume de logs (base para otimizar ingestao)?",
        query=("fetch logs\n"
               "| summarize registros = count(), by:{dt.system.bucket}\n"
               "| sort registros desc\n"
               "| limit 15"),
        visualization="categoricalBarChart", source_kind="fetch", filter_object="logs",
        width=12, height=7, section="Logs",
        requires=["logs"],
        keywords=["bucket", "ingestao", "volume", "custo", "retencao", "otimizar"],
        priority=58, visualization_settings=BARS,
    ),
]



CATALOG_BY_ID = {bp.bp_id: bp for bp in CATALOG}


def by_domain(domain):
    return [bp for bp in CATALOG if bp.domain == domain]


def domains():
    seen = []
    for bp in CATALOG:
        if bp.domain not in seen:
            seen.append(bp.domain)
    return seen
