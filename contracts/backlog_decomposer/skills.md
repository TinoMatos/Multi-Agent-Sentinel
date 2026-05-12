```yaml
habilidades:
  - nome: analisar_objetivo
    descricao: identifica dominios e capacidades implicitas no objetivo
    entrada:
      objetivo: string
    saida:
      dominios: list

  - nome: gerar_epicos
    descricao: gera epicos baseados nos dominios identificados
    entrada:
      dominios: list
    saida:
      epicos: list

  - nome: detalhar_stories
    descricao: detalha cada epico em stories com criterio de aceite
    entrada:
      epicos: list
    saida:
      stories_por_epico: object

  - nome: avaliar_riscos
    descricao: avalia riscos tecnicos e de produto do backlog proposto
    entrada:
      epicos: list
    saida:
      riscos: list

  - nome: gerar_perguntas
    descricao: identifica ambiguidades e gera perguntas de esclarecimento
    entrada:
      objetivo: string
      epicos: list
    saida:
      perguntas: list

  - nome: montar_backlog
    descricao: consolida tudo em markdown final renderizavel
    entrada:
      objetivo: string
      dominios: list
      epicos: list
      riscos: list
      perguntas: list
    saida:
      markdown: string
```
