```yaml
memoria_curta:
  guardar:
    - objetivo
    - dominios
    - epicos
    - riscos
    - perguntas
  descartar:
    - prompt_sistema_completo
    - resposta_bruta_llm        # ja parseada para Backlog dataclass
  max_registros: 6              # uma entrada por skill

resumo_final:
  max_linhas: 4
  campos:
    - objetivo
    - qtde_epicos
    - qtde_stories
    - modo                       # llm | deterministico
```
