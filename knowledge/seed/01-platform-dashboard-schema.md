# Schema de dashboards da plataforma Dynatrace (Grail / app Dashboards)

Fontes: `Dynatrace/dynatrace-for-ai` -> `skills/dt-app-dashboards`,
docs.dynatrace.com -> "Dashboards" e "API for Dashboards and Notebooks".

Dashboards da plataforma sao **documentos JSON** guardados no Document Store.
O envelope enviado para a API tem `name`, `type: "dashboard"` e `content`:

```json
{
  "name": "Nome do dashboard",
  "type": "dashboard",
  "content": {
    "version": 21,
    "variables": [],
    "tiles":   { "<id>": { "type": "data|markdown", "...": "..." } },
    "layouts": { "<id>": { "x": 0, "y": 0, "w": 24, "h": 8 } },
    "settings": { "gridLayout": { "columnsCount": 24 } }
  }
}
```

Regras estruturais:

- Cada chave em `tiles` precisa de uma chave equivalente em `layouts`.
- A grade tem **24 colunas**. Larguras usuais: 24 (linha inteira), 12 (metade),
  8 (um terco), 6 (um quarto).
- Alturas usuais: `h: 1-2` para cabecalhos markdown, `h: 5-8` para graficos,
  `h: 10-16` para tabelas detalhadas.
- Tiles nao podem se sobrepor; `x + w` nao pode passar de 24.
- Propriedades opcionais de `content`: `settings`, `refreshRate`, `annotations`.

## Tipos de tile

```json
{ "type": "markdown", "content": "# Titulo da secao" }
```

```json
{
  "type": "data",
  "title": "Nome do tile",
  "query": "timeseries avg(dt.host.cpu.usage), by:{host.name}",
  "visualization": "lineChart",
  "visualizationSettings": {},
  "querySettings": {}
}
```

Opcionais no tile de dados: `description`, `customLinkSettings`, `davis`,
`davisCopilot`, `timeframe`, `segments`.

Outros tipos: `code` (`input` com JavaScript) e `slo` (`input` com o id do SLO).

## Visualizacoes e requisitos de campos

| Familia | Visualizacoes | Requisito da query |
|---|---|---|
| Serie temporal | `lineChart`, `areaChart`, `barChart`, `bandChart` | precisa de `timeseries`/`makeTimeseries` (campos `timeframe` + `interval` + arrays numericos) |
| Categorica | `categoricalBarChart`, `pieChart`, `donutChart` | `summarize <agg>, by:{categoria}` (valor numerico + categoria) |
| Valor unico | `singleValue`, `meterBar`, `gauge` | um unico registro numerico |
| Tabular | `table`, `raw`, `recordList` | qualquer formato |
| Distribuicao | `histogram`, `honeycomb` | `histogram` exige campo do tipo range |
| Mapas | `choroplethMap`, `dotMap`, `connectionMap`, `bubbleMap` | codigo ISO 3166 ou lat/lon |
| Matriz | `heatmap`, `scatterplot` | eixos string/range (heatmap nao aceita `timestamp` cru: use `toString(bin(timestamp, 1h))`) |

Erros classicos:

- usar `barChart` com `summarize ... by:{categoria}` (sem eixo de tempo) - o
  correto e `categoricalBarChart`;
- usar `singleValue` com resultado de `timeseries` sem reduzir para escalar
  (`arrayAvg`, `arraySum`, ...);
- filtrar intervalo de tempo dentro da query - quem manda no periodo e o seletor
  de tempo do dashboard.

## visualizationSettings mais usados

- Comum: `legend`, `tooltip`, `zoom`, `unitsOverrides`, `coloring`, `thresholds`.
- `singleValue`: `{"singleValue": {"recordField": "<campo>", "label": "...",
  "colorThresholdTarget": "value", "isIconVisible": true}}`.
- `donutChart`/`pieChart`: `{"chartSettings": {"circleChartSettings":
  {"valueType": "relative"}}}`.
- `lineChart`: `{"chartSettings": {"xAxisScaling": "analyzedTimeframe",
  "legend": {"position": "bottom"}}}`.
- Limiares (thresholds) usam as variaveis de cor do design system:
  `var(--dt-colors-charts-status-ideal-default, #2f6862)`,
  `...-warning-default, #eea53c`, `...-critical-default, #c62239`.

## unitsOverrides

```json
{"identifier": "avg(dt.service.request.response_time)", "unitCategory": "time",
 "baseUnit": "microsecond", "displayUnit": null, "decimals": null,
 "suffix": "", "delimiter": false, "added": 1770204632795}
```
