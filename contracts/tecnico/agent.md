```yaml
nome: tecnico
descricao: confirmacao ATIVA do incidente — le o log via filesystem MCP, navega na URL via playwright MCP, opcionalmente busca no codigo via github MCP
tipo: task_based

objetivo: confirmar_hipotese_com_evidencia_externa_ao_mongo

contrato_saida:
  formato: json
  campos_obrigatorios:
    - tipo                 # playwright | filesystem | github
    - ref
    - nota
  exemplo:
    - { tipo: filesystem, ref: "data/logs/acme.log:5", nota: "TypeError em resolveTenant as 14:28:11Z" }
    - { tipo: playwright, ref: "https://example.com/login", nota: "HTTP 500 confirmado, body vazio" }
```

Regra do agente (em `agents/tecnico.py:34`): reportar ZERO itens quando filesystem ou playwright funcionou é ERRO. A confirmação ativa via MCP é o ponto do agente — não basta repetir o que o Mongo já disse.
