```yaml
ganchos:
  antes_da_etapa: log
  apos_etapa: log
  antes_da_acao: log         # MCPs sao caros e lentos — visibilidade ajuda no debug
  apos_acao: log
  em_erro: alerta            # asyncio.TimeoutError cai em fallback deterministico silenciosamente — deveria alertar
```

Latência típica observada: filesystem ~1s, playwright ~5–15s (boot do chromium), github ~2–4s.
