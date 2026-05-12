```yaml
ferramentas_obrigatorias:
  - montar_backlog         # ultima skill da ordem — sem ela nao ha entrega final

limites:
  max_etapas: 6            # uma por skill da ordem fixa
  limite_tempo_segundos: 60
  chamadas_ferramenta:
    analisar_objetivo: 1
    gerar_epicos: 1
    detalhar_stories: 1
    avaliar_riscos: 1
    gerar_perguntas: 1
    montar_backlog: 1
    total: 6

acoes_sensiveis: []        # apenas geracao de texto — sem efeito colateral

politicas:
  - skills aplicadas em ordem fixa: analisar_objetivo -> gerar_epicos -> detalhar_stories -> avaliar_riscos -> gerar_perguntas -> montar_backlog
  - LLM deve responder APENAS JSON puro (sem markdown, sem ```json)
  - fallback deterministico quando OPENROUTER_API_KEY ausente — esqueleto generico baseado em palavras-chave do objetivo
  - max 2-4 dominios, 2-4 epicos com 2-3 stories cada, 3-5 riscos, 2-4 perguntas
  - todo epico deve ter pelo menos 1 story com criterio_aceite
```
