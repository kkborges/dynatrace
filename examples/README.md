# Exemplos

| Pasta | Conteudo |
|---|---|
| `requirements/` | Descricoes de necessidade prontas para usar com `dtdash plan --file` |
| `templates/` | Dashboards de exemplo que a base de conhecimento indexa e que podem ser usados como template base |

Tudo que estiver nesta pasta e indexado pela base de conhecimento
(`dtdash kb status`) e pode ser reutilizado no planejamento. Para trazer
arquivos de fora:

```bash
dtdash kb add /caminho/para/meus-dashboards
```

ou envie pela interface web (aba **Conhecimento** -> enviar arquivos).
