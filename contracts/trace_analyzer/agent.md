```yaml
nome: trace_analyzer
descricao: agente deterministico que le data/traces/*.json e reporta KPIs do sistema (taxa de aprovacao Critic, confianca media, evidencias degradadas)
tipo: task_based       # determinista — sem LLM

objetivo: medir_saude_do_sistema_a_partir_de_execucoes_passadas

contrato_saida:
  formato: relatorio
  campos_obrigatorios:
    - total_execucoes
    - taxa_aprovacao_critic
    - confianca_media
    - evidencias_degradadas_pct
    - por_cliente
    - motivos_veto_mais_comuns
  exemplo: |
    # Trace Analyzer — 8 execucao(oes)

    - Aprovados pelo Critic: 5/8 (62%)
    - Vetados pelo Critic:   3/8
    - Confianca media:       73%
    - Iteracoes (media):     5.5
    - Re-delegacoes total:   3
    - Evidencias degradadas: 14/40 (35%)
```
