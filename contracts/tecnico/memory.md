```yaml
memoria_curta:
  guardar:
    - hipotese                # contexto que veio da Triagem
    - tool_results_parsed     # so a lista de evidencias final, nao o tool_use raw
  descartar:
    - prompt_sistema_completo # SYSTEM do _build_system() — repete em toda invocacao
    - chromium_logs           # ruido do Playwright
    - paginas_html_brutas     # so o que virou nota de evidencia importa
  max_registros: 10

resumo_final:
  max_linhas: 3
  campos:
    - evidencias_filesystem
    - evidencias_playwright
    - evidencias_github
```
