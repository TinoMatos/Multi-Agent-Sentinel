```yaml
nome: rca_writer
descricao: renderiza o RCA final em markdown (template local) e salva em reports/rca_<ticket_id>.md
tipo: task_based       # funcao pura — sem LLM

objetivo: produzir_artefato_markdown_versionavel

contrato_saida:
  formato: relatorio
  campos_obrigatorios:
    - cabecalho          # cliente, timestamp UTC, confianca, iteracoes
    - pergunta_original
    - conclusao
    - tabela_evidencias  # # | tipo | ref | nota
    - ressalvas          # motivos do Critic (se houver)
  exemplo: |
    # RCA — Acme Corp

    _Gerado em 2026-05-12 14:32 UTC pelo Multi-Agent Sentinel_

    **Pergunta original:** Por que o sistema da Acme esta caindo?

    **Confianca:** 85%  |  **Iteracoes:** 1

    ## Conclusao
    Incidente correlacionado ao deploy `abc123`. Recomenda-se rollback imediato.

    ## Evidencias
    | # | Tipo | Referencia | Nota |
    |---|---|---|---|
    | 1 | `mongo` | `ticket-id` | Site fora do ar |
    | 2 | `playwright` | `https://acme.example` | HTTP 500 confirmado |
```
