# APIs da plataforma usadas para criar dashboards e segments

Fonte: developer.dynatrace.com -> "Access platform APIs from outside",
"Document service"; docs.dynatrace.com -> "API for Dashboards and Notebooks".

Base das APIs de plataforma: `https://<env-id>.apps.dynatrace.com/platform/...`
(o catalogo completo fica em `/platform/swagger-ui/index.html` do proprio tenant).

## Autenticacao

1. **Platform token** (`dt0s16.*`): enviar direto em
   `Authorization: Bearer dt0s16...`.
2. **OAuth client credentials**:

```bash
curl -X POST 'https://sso.dynatrace.com/sso/oauth2/token' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode 'client_id=dt0s02...' \
  --data-urlencode 'client_secret=dt0s02...' \
  --data-urlencode 'scope=document:documents:write storage:filter-segments:write ...' \
  --data-urlencode 'resource=urn:dtaccount:<account-uuid>'
```

Escopos necessarios para o fluxo completo do dtdash:

- `document:documents:read`, `document:documents:write`, `document:documents:delete`
- `document:environment-shares:write` (compartilhar com o ambiente)
- `storage:filter-segments:read`, `:write`, `:share`
- leitura Grail: `storage:logs:read`, `storage:metrics:read`, `storage:events:read`,
  `storage:spans:read`, `storage:bizevents:read`, `storage:entities:read`,
  `storage:system:read`, `storage:user.sessions:read`, `storage:user.events:read`,
  `storage:security.events:read`, `storage:buckets:read`

## Documentos (dashboards)

| Operacao | Chamada |
|---|---|
| Listar | `GET /platform/document/v1/documents?filter=type=='dashboard'` |
| Criar | `POST /platform/document/v1/documents` (multipart: `name`, `type=dashboard`, `content`) |
| Ler conteudo | `GET /platform/document/v1/documents/{id}/content` |
| Atualizar | `PATCH /platform/document/v1/documents/{id}?optimistic-locking-version=N` |
| Excluir | `DELETE /platform/document/v1/documents/{id}` |
| Compartilhar com o ambiente | `POST /platform/document/v1/environment-shares` `{"documentId": "...", "access": "read"}` |

Limite de conteudo: 50 MB por documento.
URL do dashboard criado:
`https://<env>.apps.dynatrace.com/ui/apps/dynatrace.dashboards/dashboard/<id>`.

## Grail / DQL

| Operacao | Chamada |
|---|---|
| Validar sintaxe | `POST /platform/storage/query/v1/query:verify` `{"query": "..."}` |
| Executar | `POST /platform/storage/query/v1/query:execute` `{"query": "...", "maxResultRecords": 100}` |
| Buscar resultado | `GET /platform/storage/query/v1/query:poll?request-token=<token>` |
| Cancelar | `POST /platform/storage/query/v1/query:cancel` |

A execucao e assincrona: se a resposta vier com `state != "SUCCEEDED"`, use o
`requestToken` no `query:poll`. O resultado fica disponivel por cerca de 1 minuto
apos concluir.

## Segments

| Operacao | Chamada |
|---|---|
| Listar (leve) | `GET /platform/storage/filter-segments/v1/filter-segments:lean` |
| Criar | `POST /platform/storage/filter-segments/v1/filter-segments` |
| Atualizar | `PUT/PATCH .../filter-segments/{uid}` (bloqueio otimista por `version`) |
