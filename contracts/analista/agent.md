```yaml
nome: analista
descricao: consulta MongoDB para contexto de cliente, tickets abertos, erros correlacionados e RCAs historicos similares
tipo: task_based       # funcoes puras deterministicas — sem LLM

objetivo: trazer_contexto_estruturado_do_incidente

contrato_saida:
  formato: json
  campos_obrigatorios:
    - tipo               # mongo | erro | rca_historico | commit
    - ref
    - nota
  exemplo:
    - { tipo: mongo, ref: "ticket-id", nota: "Site fora do ar" }
    - { tipo: erro, ref: "erro-id", nota: "TypeError freq=42" }
    - { tipo: rca_historico, ref: "rca-id", nota: "regressao do mesmo bug em deploy anterior" }
    - { tipo: commit, ref: "abc123def", nota: "deploy suspeito do ticket" }
```

Funções expostas em [agents/analista.py](agents/analista.py): `cliente_por_nome`, `tickets_abertos_do_cliente`, `erros_do_ticket`, `rcas_similares`, `registrar_rca`.
