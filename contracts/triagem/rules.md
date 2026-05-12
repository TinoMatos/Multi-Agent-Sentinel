```yaml
ferramentas_obrigatorias:
  - call_analista          # sem Mongo nao tem cliente/ticket — base do RCA
  - call_critic            # anti-alucinacao: nada publica sem veredito
  - call_rca_writer        # artefato final em reports/

limites:
  max_etapas: 8            # SENTINEL_MAX_ITERATIONS — caminho natural usa 5, deixa 3 pra 1 retry
  token_budget: 50000      # SENTINEL_TOKEN_BUDGET
  limite_tempo_segundos: 180  # soma dos timeouts dos sub-agentes
  chamadas_ferramenta:
    call_analista: 2       # delegacao paralela 1x; re-delegacao se confianca<80%
    call_observabilidade: 2
    call_tecnico: 2
    call_critic: 1
    call_rca_writer: 1
    total: 8

acoes_sensiveis:
  - registrar_rca          # analista.registrar_rca — INSERT rcas + UPDATE ticket.status=fechado (irreversivel sem re-seed)
  - salvar                 # rca_writer.salvar — escreve em reports/rca_<ticket_id>.md (sobrescreve)

politicas:
  - so confirmar com Tecnico quando ha ticket aberto (sem ticket: bail direto pro Critic)
  - delegacao Analista + Observabilidade roda em paralelo (asyncio.gather)
  - sem Grafana real, confianca fica capada em 70% (degradado)
  - so registrar_rca quando veredito.aprovado=true E inv.ticket existe
  - output_guard.sanitize deve rodar antes de qualquer escrita (PII/segredos)
  - confianca >= 0.8 confirma; < 0.8 re-delega para CONFIRMANDO (Tecnico) — maximo 1 retry por investigacao
  - apos RCA aprovado, chamar backlog_decomposer com a conclusao como objetivo (opt-out via SENTINEL_GERAR_BACKLOG=0)
  - falha do backlog NAO derruba a investigacao — incidente ja foi resolvido
  - modo interactive: se cliente nao identificado, perguntar ao humano antes de bail em "cliente nao encontrado"
  - modo interactive: pedir confirmacao s/n antes de registrar_rca (acao sensivel — fecha ticket no Mongo)
  - negacao humana encerra com encerrado_por_humano=True; markdown ainda eh salvo (transparencia)
```
