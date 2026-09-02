# DPS, Grail e analise por logs

Fonte: `Dynatrace/dynatrace-for-ai` -> `skills/dt-platform-costs`;
docs.dynatrace.com -> "Dynatrace Platform Subscription".

## Como o dtdash detecta DPS

Consumo de plataforma e registrado em `dt.system.events` com
`event.kind == "BILLING_USAGE_EVENT"`, segmentado por `event.type`
(capacidade consumida). A sonda usada e:

```dql
fetch dt.system.events, from:-24h
| filter event.kind == "BILLING_USAGE_EVENT"
| summarize events = count(), by:{event.type}
| sort events desc
| limit 10
```

Interpretacao correta (regra da propria Dynatrace):

- houve registros -> o tenant **esta consumindo** sob DPS: vale explorar
  logs/Grail e tiles de consumo;
- nao houve registros -> **nao conclua** que falta licenca. Eventos de billing
  medem consumo, nunca entitlement. Entitlement se confirma em
  *Account Management > Subscription*.

## Tiles de consumo (somente quando DPS foi detectado)

```dql
// consumo por capacidade nos ultimos 7 dias
fetch dt.system.events, from:-7d
| filter event.kind == "BILLING_USAGE_EVENT"
| summarize uso = sum(billed_bytes), by:{event.type}
| sort uso desc

// custo de consulta por origem (quem varre mais dados)
fetch dt.system.events, from:-7d
| filter event.kind == "BILLING_USAGE_EVENT" and event.type == "Query"
| summarize gib = sum(billed_bytes) / 1073741824.0, by:{query_source}
| sort gib desc
| limit 20
```

Nunca apresente peso de normalizacao como valor em dolar: rankings sao
relativos; numeros oficiais ficam em *Account Management > Subscription >
Cost and usage details*.

## Analise por logs no Grail

Com DPS/Grail, logs deixam de ser so texto e viram fonte analitica:

```dql
// erros por servico (serie temporal)
fetch logs
| filter matchesValue(loglevel, {"ERROR", "SEVERE", "CRITICAL"})
| makeTimeseries erros = count(), by:{service.name}

// extrair campo de um log semi-estruturado e agrupar
fetch logs
| filter matchesPhrase(content, "payment declined")
| parse content, "LD 'code=' INT:codigo"
| summarize ocorrencias = count(), by:{codigo}
| sort ocorrencias desc

// distribuicao de severidade
fetch logs
| summarize registros = count(), by:{loglevel}
| sort registros desc
```

Boas praticas de custo em dashboards baseados em log:

- filtre por bucket/servico/namespace antes de agregar;
- prefira `summarize`/`makeTimeseries` a tabelas cruas de milhares de linhas;
- limite tabelas com `limit`;
- use segments para nao repetir os mesmos filtros em cada tile.
