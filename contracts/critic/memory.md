```yaml
memoria_curta:
  guardar:
    - conclusao
    - motivos_heuristica
    - contradicoes_llm
    - veredito_final
  descartar:
    - prompt_critic_completo
    - evidencias_repetidas       # ja vieram da Triagem, nao duplicar
  max_registros: 5

resumo_final:
  max_linhas: 2
  campos:
    - aprovado
    - motivos
```
