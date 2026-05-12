# Análise de agente — execução real vs. contrato

> Investigação: `python -m agents.triagem "Por que o sistema da Acme esta caindo?"`
> Resultado: rca_id=6a033f446293fde3fb36e88a · confiança=70% · iter=5
> Modo: **degradado** (Playwright/Grafana/filesystem MCPs caíram em fallback)

---

## Veredicto rápido

| Pergunta | Resposta |
|---|---|
| Taxa de sucesso 100%? | ✅ RCA publicado, Critic aprovou |
| Ferramentas obrigatórias chamadas? | ❌ **não** — Técnico não chamou `filesystem.read_text_file` nem `playwright.browser_navigate` (cairam em fallback determinístico) |
| Pipeline completo? | ⚠️ rodou os 5 estados (HIPOTESE→COLETANDO→CONFIRMANDO→VALIDANDO→PUBLICANDO), mas **iter=5 = max_iterations** — loop não foi por escolha, foi por trava |
| Sem anomalias? | ❌ 3 das 6 evidências marcadas `(degradado)`; confiança capada em 70% por falta de Grafana real |

---

## Divergências contrato vs. realidade

### Triagem
- **`rules.md` diz `max_etapas: 5`** → execução chegou em `iter=5` (limite). Não foi parada por `objetivo_alcancado`; foi por `max_etapas_excedido`. O loop não tem critério de saída antecipada quando confiança estagna.
- **`rules.md` lista `call_critic` e `call_rca_writer` como obrigatórias** → ambas foram chamadas. ✅
- **Política "confiança ≥ 0.8 confirma; < 0.8 re-delega"** → **não cumprida**. Confiança ficou em 0.70 (capada) e o loop só consumiu iterações sem re-delegar Analista/Observabilidade. State machine não tem transição `VALIDANDO → COLETANDO`.

### Técnico
- **`rules.md.ferramentas_obrigatorias: [filesystem.read_text_file, playwright.browser_navigate]`** → nenhuma foi chamada via MCP. As evidências `playwright` e `filesystem` saíram do fallback determinístico em [triagem.py:117](agents/triagem.py#L117), não do agente Técnico.
- **`agent.md` "reportar ZERO itens quando filesystem ou playwright funcionou é ERRO"** → não se aplica porque nenhum funcionou. Mas o sistema não distingue "MCP indisponível" de "MCP falhou" — ambos viram `(degradado)` silenciosamente.

### Critic
- **`rules.md` "veto definitivo: aprovado=false impede registrar_rca"** → Critic aprovou. Mas as heurísticas atuais ([critic.py:23](agents/critic.py#L23)) não detectam `(degradado)` na nota. Sugestão: adicionar heurística `"> 50% das evidências marcadas degradado → motivo"`.
- Conclusão cita deploy → tem evidência `tipo=commit` ✅
- Conclusão não cita métrica → não precisa de Grafana real ✅ (mas a confiança já foi capada)

### Observabilidade
- **`rules.md.ferramentas_obrigatorias: [grafana.list_alerts]`** → não chamada. Caiu no fallback que lê `grafana_alert_id` do Mongo. A evidência aparece como `tipo=grafana` mesmo sem Grafana ter respondido — confuso.

### Analista
- **`rules.md` "rcas_similares SEMPRE com client_id ou tipo_erro"** → cumprido em [triagem.py:64](agents/triagem.py#L64). ✅
- **`acoes_sensiveis: [registrar_rca]`** → executado sem confirmação humana. Gap conhecido.

### RCA Writer
- ✅ Cumpriu tudo. Markdown gerado, salvo em `reports/rca_6a033f44…md`.

---

## 3 ajustes que o contrato exige e o código não entrega

1. **Re-delegação real** (gap #1 da primeira análise) — adicionar transição `VALIDANDO → COLETANDO` em [triagem.py:302](agents/triagem.py#L302) quando `confianca < 0.8` E `iteracao < max_iterations`.
2. **Heurística "degradado" no Critic** — em `_heuristicas()`, contar quantas evidências têm `"degradado"` na nota; se > 50%, adicionar motivo `"maioria das evidências em modo degradado — confiança não validada externamente"`.
3. **Distinguir MCP-indisponível de MCP-falhou** — hoje os dois caem no mesmo `pass` silencioso. Logar/anotar a causa real (timeout vs. FileNotFoundError vs. resposta vazia) e refletir na evidência.

---

## O que o contract-driven development revelou aqui

Sem os `.md`, esses 3 problemas estão diluídos no código e parecem "comportamento esperado em modo degradado". Com os contratos escritos, fica explícito: o sistema **prometeu** chamar `filesystem.read_text_file` (Técnico/rules.md) e **não chamou**. A divergência é factual, não opinião.

> Não é debugar código. É iterar sobre especificação. 