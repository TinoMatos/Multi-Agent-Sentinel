```yaml
ferramentas_obrigatorias:
  - heuristicas                # checagens deterministicas — sempre rodam
  # sanity_llm e opcional — sem OPENROUTER_API_KEY cai pra heuristica pura

limites:
  max_etapas: 2                # heuristica + 1 chamada LLM
  limite_tempo_segundos: 30
  chamadas_ferramenta:
    heuristicas: 1
    sanity_llm: 1              # maximo 3 contradicoes no JSON de saida
    total: 2

acoes_sensiveis: []            # somente leitura — nao escreve no Mongo nem em reports/

politicas:
  - veto e definitivo: aprovado=false impede registrar_rca (mas RCA ainda eh renderizado em reports/ com ressalvas)
  - "LLM deve responder APENAS JSON {contradicoes: [str, ...]} — texto livre eh ignorado"
  - sanity_llm corta evidencias em 3000 chars para nao estourar prompt
  - cada motivo derruba confianca em 20% (deterministico) ou 25% (heuristica pura via avaliar() sync)
  - parsing tolerante: extrai entre primeiro "{" e ultimo "}" — se falhar, ignora silenciosamente
```
