```yaml
ferramentas_obrigatorias:
  - render_rca                 # gera o markdown
  - salvar                     # escreve em reports/

limites:
  max_etapas: 2                # render + salvar
  limite_tempo_segundos: 5
  chamadas_ferramenta:
    render_rca: 1
    salvar: 1
    total: 2

acoes_sensiveis:
  - salvar                     # escreve em reports/rca_<ticket_id>.md — sobrescreve se ja existe

politicas:
  - output_guard.sanitize deve rodar ANTES de salvar (PII/segredos) — feito pela Triagem em PUBLICANDO
  - REPORTS_DIR criado on-demand (mkdir exist_ok=True)
  - nome do arquivo SEMPRE rca_<ticket_id>.md — re-execucao sobrescreve o anterior
  - timestamp em UTC (datetime.now(timezone.utc)) para nao depender de timezone local
  - ressalvas do Critic aparecem mesmo quando aprovado=false (RCA fica registrado, marcado)
```
