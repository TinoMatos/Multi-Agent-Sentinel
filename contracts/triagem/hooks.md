```yaml
ganchos:
  antes_da_etapa: log       # _snapshot() em agents/triagem.py:267 — registra estado, iteracao, confianca, elapsed_s
  apos_etapa: log
  antes_da_acao: log        # antes de cada call_* — util para medir latencia por sub-agente
  apos_acao: log            # registra qtde de evidencias retornadas
  em_erro: alerta           # BudgetExceeded, asyncio.TimeoutError — sao engolidos hoje, mas deveriam alertar
```

Implementado em [agents/_telemetria.py](agents/_telemetria.py). O `historico_estados` da `Investigacao` é o trace consumível pelo Streamlit.
