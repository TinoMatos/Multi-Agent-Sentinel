```yaml
nome: critic
descricao: valida se as evidencias coletadas sustentam a conclusao — heuristica deterministica + sanity check LLM (modelo fast)
tipo: task_based

objetivo: vetar_rcas_alucinados_antes_de_publicar

contrato_saida:
  formato: json
  campos_obrigatorios:
    - aprovado           # bool
    - confianca          # 0.0–1.0
    - motivos            # lista de contradicoes; vazia quando aprovado
  exemplo:
    aprovado: false
    confianca: 0.55
    motivos:
      - "conclusao cita deploy mas nao ha evidencia tipo=commit"
      - "contradicao LLM: stacktrace aponta para auth, conclusao fala de billing"
```

Heurísticas em [agents/critic.py:23](agents/critic.py#L23): <2 evidências, conclusão fala de deploy sem `tipo=commit`, conclusão cita métrica sem `tipo=grafana`.
