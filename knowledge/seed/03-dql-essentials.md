# DQL essencial para tiles de dashboard

Fonte: `Dynatrace/dynatrace-for-ai` -> `skills/dt-dql-essentials`.

## Comando de entrada por modelo de dado

| Comando | Modelo | Campos-chave |
|---|---|---|
| `fetch logs` | logs | `content` (mensagem), `loglevel` (severidade, **nao** `log.level`), `k8s.*`, `host.name`, `service.name` |
| `fetch spans` | tracing | `span.*`, `service.name`, `http.*`, `db.*`; tempo em `start_time`/`end_time` (nao existe `timestamp`) |
| `fetch events` / `fetch dt.davis.events` | eventos | `event.kind`, `event.type`, `event.category` |
| `fetch dt.davis.problems` | problemas | `event.status`, `display_id`, campos `k8s.*` sao **arrays** (use `in()`) |
| `fetch bizevents` | eventos de negocio | `event.type`, campos do dominio |
| `fetch user.sessions` / `fetch user.events` | RUM | `dt.rum.*`, `browser.*`, `geo.*`, `useraction.*` |
| `fetch security.events` | seguranca | `vulnerability.*`, `event.*` |
| `fetch dt.system.events` | eventos de sistema/billing | `event.kind == "BILLING_USAGE_EVENT"` |
| `timeseries agg(metrica)` | metricas | **nao** existe `fetch dt.metric`; chaves com hifen precisam de crase |
| `smartscapeNodes TIPO` | topologia | `HOST`, `SERVICE`, `K8S_CLUSTER`, `K8S_NAMESPACE`, ... |

`dt.entity.*` esta **descontinuado** em queries novas: prefira `dt.smartscape.*`
e `smartscapeNodes`.

Descoberta: `fetch dt.system.data_objects | fields name, type` e
`describe <objeto>` listam objetos e campos reais do tenant.

## Armadilhas de sintaxe (as que mais quebram tiles)

| Errado | Certo | Motivo |
|---|---|---|
| `filter campo in ["a","b"]` | `filter in(campo, {"a","b"})` | `[]` delimita subquery, nao array literal |
| `by: a, b` | `by: {a, b}` | listas de campos usam chaves |
| `filter nome == "*app*"` | `filter matchesValue(nome, "*app*")` | `==` nao aceita curinga |
| `filter log.level == "ERROR"` | `filter loglevel == "ERROR"` | campo de severidade e `loglevel` |
| `sort count() desc` | ``sort `count()` desc`` | nomes com parenteses precisam de crase |
| `by: {bin(timestamp, 1h)}` + `sort` pelo nome gerado | `by: {t = bin(timestamp, 1h)}` + `sort t` | sempre nomeie a chave de agrupamento |
| `length(campo)` | `stringLength(campo)` | funcao inexistente |
| `metrics dt.host.cpu.usage` | `timeseries avg(dt.host.cpu.usage)` | `metrics` traz metadados, nao valores |
| `percentile()` em `timeseries` sem `rollup:` | `timeseries p90 = percentile(m, 90), rollup: avg` | sem `rollup` volta vazio |
| `rollup:` em `summarize` | remover | `rollup:` so existe em `timeseries` |

## Padroes uteis

```dql
// serie temporal por dimensao
timeseries avg(dt.host.cpu.usage), by:{host.name}

// taxa de erro de servicos (spans)
fetch spans
| filter isNotNull(request.is_failed)
| summarize total = count(), falhas = countIf(request.is_failed == true), by:{service.name}
| fieldsAdd taxa_erro = 100.0 * falhas / total
| sort taxa_erro desc
| limit 20

// volume de logs de erro ao longo do tempo
fetch logs
| filter matchesValue(loglevel, {"ERROR", "SEVERE", "CRITICAL"})
| makeTimeseries erros = count(), by:{service.name}

// top mensagens de erro
fetch logs
| filter matchesValue(loglevel, {"ERROR", "SEVERE", "CRITICAL"})
| summarize ocorrencias = count(), by:{content_pattern = punctuation(content)}
| sort ocorrencias desc
| limit 20
```

## Custo e desempenho (Grail)

- Filtre cedo (bucket, campo indexado, `filter` antes de `parse`/`summarize`).
- Use `fields`/`fieldsKeep` para reduzir colunas.
- `samplingRatio:` em `fetch` reduz o volume lido em analises exploratorias.
- Em dashboards, evite `fetch` sem filtro em janelas longas: cada refresh custa
  consumo de query no DPS.
