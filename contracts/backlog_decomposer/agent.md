```yaml
nome: backlog_decomposer
descricao: agente goal_oriented que transforma um objetivo amplo de produto em backlog (dominios, epicos, stories, riscos, perguntas)
tipo: goal_oriented        # encadeia 6 skills em ordem fixa

objetivo: decompor_objetivo_em_backlog_executavel

contrato_saida:
  formato: relatorio
  campos_obrigatorios:
    - objetivo
    - dominios
    - epicos               # cada um com stories + criterio_aceite
    - riscos
    - perguntas
  exemplo: |
    # Backlog — permitir cadastro sem suporte humano

    ## Dominios identificados
    - fluxo de usuario
    - infraestrutura
    - observabilidade

    ## Epicos e stories
    ### Epico 1: Fluxo principal de cadastro
    - **Definir jornada feliz** — criterio: diagrama validado com produto

    ## Riscos
    - dependencia oculta com sistemas legados pode aparecer tarde

    ## Perguntas
    - Qual o publico-alvo concreto?
```

Sibling agent — não integra com Triagem. Domínio diferente (produto/engenharia vs. incident response). CLI dedicada: `python -m agents.backlog_decomposer "..."`.
