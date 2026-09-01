# Templates de exemplo

Coloque aqui dashboards da plataforma Dynatrace (JSON exportado pelo app
Dashboards ou obtido via Document API) para que o dtdash os indexe e possa
usa-los como base:

```bash
dtdash plan "..." --base examples/templates/exemplo-servicos.json
```

Formato aceito:

* documento completo -> `{"name": ..., "type": "dashboard", "content": {...}}`
* apenas o conteudo -> `{"version": 21, "tiles": {...}, "layouts": {...}}`

Dashboards no formato classico (com `dashboardMetadata`) tambem sao indexados,
mas servem apenas como referencia de conteudo - nao como base estrutural.
