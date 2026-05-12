```yaml
ferramentas_obrigatorias:
  - filesystem.read_text_file   # ler o log_path do ticket
  - playwright.browser_navigate # confirmar HTTP status da URL

limites:
  max_etapas: 6              # 1 leitura log + 1 navigate + 1 github + folga
  limite_tempo_segundos: 90  # SENTINEL_TECNICO_TIMEOUT_S (agents/triagem.py:109)
  chamadas_ferramenta:
    filesystem.read_text_file: 2
    playwright.browser_navigate: 2
    playwright.browser_snapshot: 2
    github.search_code: 3
    total: 6

acoes_sensiveis: []          # leitura apenas — proibido escrever

politicas:
  - filesystem MCP esta rooted em ./data — converter "data/logs/x.log" -> "logs/x.log"
  - github MCP so com SENTINEL_USE_GITHUB=1 E SENTINEL_GITHUB_REPO setado
  - github: APENAS search_code; NUNCA get_commit/get_pull_request (SHAs do seed sao ficticios)
  - github: NUNCA escrever (sem create issue, sem comment, sem push)
  - saida deve ser lista JSON pura na ULTIMA mensagem (sem markdown, sem ```json)
  - maximo 6 itens de evidencia
  - se timeout estourar, cair em fallback deterministico (so quando ha deploy_suspeito)
```
