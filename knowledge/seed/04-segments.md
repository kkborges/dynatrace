# Segments (filter-segments) - organizar o contexto do dashboard

Fontes: docs.dynatrace.com -> "Segments"; SDK
`@dynatrace-sdk/client-filter-segment-management`; API
`/platform/storage/filter-segments/v1/filter-segments`.

Um segment guarda, de forma reutilizavel, o **recorte de dados** (ambiente,
squad, cluster, namespace, aplicacao, cliente) e pode ser aplicado a dashboards,
notebooks e apps sem reescrever filtros em cada tile.

## Payload de criacao (POST)

```json
{
  "name": "producao-pagamentos",
  "description": "Namespace de pagamentos no cluster de producao",
  "isPublic": true,
  "includes": [
    { "dataObject": "logs",  "filter": "k8s.namespace.name == \"pagamentos\"" },
    { "dataObject": "spans", "filter": "k8s.namespace.name == \"pagamentos\"" },
    { "dataObject": "events","filter": "k8s.namespace.name == \"pagamentos\"" }
  ],
  "variables": { "type": "query", "value": "fetch logs | limit 1" }
}
```

- `isPublic: false` -> visivel apenas ao dono; `true` -> visivel ao ambiente
  (requer o escopo `storage:filter-segments:share`).
- Escopos: `storage:filter-segments:read` / `:write` / `:share` / `:delete` /
  `:admin`.
- Resposta 201 traz `uid` e `version` (bloqueio otimista em updates).

## Como aplicar no dashboard

- Cada tile de dados aceita a propriedade opcional `segments`.
- Alternativa robusta (sempre funciona, inclusive em exports antigos): embutir o
  filtro do segment na propria DQL do tile.
- O dtdash suporta as duas estrategias (`--segment-mode tile|dql|both`).

## Campos recomendados por recorte

| Recorte | logs / spans / events | metricas (timeseries) |
|---|---|---|
| Cluster Kubernetes | `k8s.cluster.name` | `by:{k8s.cluster.name}` |
| Namespace | `k8s.namespace.name` | `by:{k8s.namespace.name}` |
| Workload | `k8s.workload.name` | `by:{k8s.workload.name}` |
| Servico | `service.name` | `by:{dt.smartscape.service}` |
| Host | `host.name` | `by:{host.name}` |
| Aplicacao RUM | `application.name` | - |
| Ambiente | `dt.host.group.id`, `environment`, tag `environment` | idem |

Campos de ambiente variam por tenant - o dtdash valida a existencia do campo com
`describe <objeto>` antes de gerar o filtro e marca como "nao verificado" quando
esta offline.
