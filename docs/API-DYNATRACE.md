# APIs Dynatrace usadas pelo dtdash

Base: `https://<environment-id>.apps.dynatrace.com/platform/...`
(o catalogo completo do proprio tenant fica em `/platform/swagger-ui/index.html`).

## Autenticacao

| Metodo | Como o dtdash usa |
|---|---|
| Platform token (`dt0s16.*`) | `Authorization: Bearer <token>` direto |
| OAuth client credentials | `POST https://sso.dynatrace.com/sso/oauth2/token` com `grant_type=client_credentials`, `scope` e `resource=urn:dtaccount:<uuid>`; o access token e cacheado ate expirar |

## Documentos (dashboards)

| Operacao | Chamada | Observacao |
|---|---|---|
| Listar | `GET /platform/document/v1/documents?filter=type=='dashboard'` | |
| Criar | `POST /platform/document/v1/documents` | multipart: `name`, `type=dashboard`, `isPrivate`, `description`, parte de arquivo `content` (JSON) |
| Ler conteudo | `GET /platform/document/v1/documents/{id}/content` | fallback para a resposta multipart de `/documents/{id}` |
| Atualizar | `PATCH /platform/document/v1/documents/{id}?optimistic-locking-version=N` | |
| Excluir | `DELETE /platform/document/v1/documents/{id}` | vai para a lixeira (30 dias) |
| Compartilhar | `POST /platform/document/v1/environment-shares` | `{"documentId": "...", "access": "read"}`; HTTP 409 = ja compartilhado |

Limite de 50 MB por documento. URL final do dashboard:
`https://<env>.apps.dynatrace.com/ui/apps/dynatrace.dashboards/dashboard/<id>`.

## Filter segments

| Operacao | Chamada |
|---|---|
| Listar (leve) | `GET /platform/storage/filter-segments/v1/filter-segments:lean` |
| Criar | `POST /platform/storage/filter-segments/v1/filter-segments` |

Payload de criacao:

```json
{
  "name": "Namespace pagamentos",
  "description": "Recorte automatico por namespace = pagamentos (dtdash)",
  "isPublic": true,
  "includes": [
    {"dataObject": "logs",  "filter": "k8s.namespace.name == \"pagamentos\""},
    {"dataObject": "spans", "filter": "k8s.namespace.name == \"pagamentos\""}
  ]
}
```

`isPublic: true` exige o escopo `storage:filter-segments:share`. Antes de criar, o
dtdash procura um segment com o mesmo nome e o reutiliza.

## Grail / DQL

| Operacao | Chamada |
|---|---|
| Validar sintaxe | `POST /platform/storage/query/v1/query:verify` |
| Executar | `POST /platform/storage/query/v1/query:execute` |
| Buscar resultado | `GET /platform/storage/query/v1/query:poll?request-token=<token>` |

A execucao e assincrona: quando `state != "SUCCEEDED"`, o cliente faz poll com o
`requestToken` ate concluir ou estourar o tempo limite. Tenants sem `query:verify`
(HTTP 404/405) caem automaticamente para validacao por execucao com `limit`.

## Deteccao de DPS

```dql
fetch dt.system.events, from:-24h
| filter event.kind == "BILLING_USAGE_EVENT"
| summarize events = count(), by:{event.type}
| sort events desc
| limit 10
```

* com registros -> consumo DPS confirmado (habilita tiles de consumo/Grail);
* sem registros -> **nao** conclua ausencia de licenca: eventos de billing medem
  consumo, nao entitlement (confirme em *Account Management > Subscription*).

## Verificacao automatica

`dtdash selftest -t <tenant>` exercita todos os endpoints desta pagina na ordem em
que a publicacao os usa. Detalhes que a bateria confirma no tenant real:

* qual chave carrega o identificador na resposta de criacao (`id`, `uid`,
  `documentId`...) — o cliente aceita todas, mas o relatorio informa qual chegou;
* se `query:verify` existe (sem ele a validacao cai para execucao com `limit`);
* se `environment-shares` existe (sem ele o share cai para `PATCH isPrivate=false`);
* se a propriedade `segments` do tile sobrevive ao round-trip de gravacao/leitura;
* quais chaves de metrica do catalogo existem neste tenant.

## Descoberta usada no planejamento

| Objetivo | DQL |
|---|---|
| Data objects disponiveis | `fetch dt.system.data_objects \| fields name, type` |
| Campos de um objeto | `describe logs` |
| Existencia de metricas | `metrics \| filter in(metric.key, {"dt.host.cpu.usage", ...}) \| fields metric.key` |
