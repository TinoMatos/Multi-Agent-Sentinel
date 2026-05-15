# Multi-Agent Technical Sentinel

Sistema multiagente que **investiga incidentes técnicos** correlacionando MongoDB + Grafana + Filesystem + Playwright + GitHub e devolve um **RCA com evidências**. Você dá o sintoma (*"Acme está fora do ar"*) — ele entrega causa, prova e backlog do fix.

**Stack:** Python 3.11+ · LangChain/LangGraph · MCPs via `langchain-mcp-adapters` · MongoDB · Streamlit · OpenRouter. Arquitetura **contract-driven**: cada agente é especificado em Markdown e validado contra o código.

---

## Pipeline

```text
Memória (longa + episódica + contextual + lições) ─┐
                                                   ▼
Triagem → [Analista (Mongo) ‖ Observabilidade (Grafana)] → Técnico (FS+Playwright+GitHub) → Critic → RCA → Backlog
              ↑                                                      │                       │
              └── re-delega se confiança < 80% E memória sem fatos ──┘                       ▼
                                                                                       Reflection
                                                                              (extrai lição se veto/baixa conf./max iter)
```

State machine, `max_iterations=8`, 1 retry. Critic veta antes de publicar (anti-alucinação). Após RCA aprovado, **Backlog Decomposer** quebra o fix em épicos+stories. **Memória de 4 camadas** (longa/episódica/contextual/lições) é consultada após identificar o cliente — quando há fatos do domínio, a redelegação é pulada (economia de ~44% das iterações com memória bem calibrada). Após `DONE`, **Reflection** extrai uma lição generalizável se a execução teve sinais de aprendizado (veto, baixa confiança, max_iter).

---

## Quick start

```bash
pip install -r requirements.txt
docker run -d -p 27017:27017 mongo                              # ou MongoDB local
mongosh "mongodb://localhost:27017/sentinel" data/seed_mongo.js
cp .env.example .env                                            # cole OPENROUTER_API_KEY=sk-or-v1-...
python -m streamlit run app.py                                  # UI em http://localhost:8501
```

**Modelos:** `:free` do OpenRouter **não funciona** com MCPs grandes — usa Anthropic pago (`claude-sonnet-4.5` + `claude-haiku-4.5`, ~$0.01–0.05 por RCA). Sem chave: roda em modo degradado determinístico.

---

## Agentes

| Agente | Tipo | Função |
| --- | --- | --- |
| Triagem | task_based / interactive | orquestrador, state machine |
| Analista | task_based | Mongo (cliente, tickets, erros, RCAs históricos) |
| Observabilidade | task_based | Grafana MCP (alertas, métricas) |
| Técnico | task_based | filesystem + playwright + github MCPs |
| Critic | task_based | heurísticas + sanity LLM, veta RCAs alucinados |
| RCA Writer | task_based + **ReAct** | renderiza markdown; `executar_react()` segue [architectures/react/planner.md](../architectures/react/planner.md) — `raciocinio` explícito, ações `CHAMAR_FERRAMENTA` / `FINALIZAR` / `PERGUNTAR_USUARIO` |
| Trace Analyzer | task_based | KPIs de `data/traces/*.json` |
| Backlog Decomposer | goal_oriented | decompõe fix em épicos+stories+riscos |

Cada um tem 5 contratos `.md` em [contracts/](contracts/). Rode `python -m contracts.validar` pra cruzar contrato com código.

---

## Comandos

```bash
python -m streamlit run app.py                            # UI (recomendado — carrega .env)
python -m agents.triagem "Por que a Acme esta caindo?"    # CLI
python -m agents.triagem "algo estranho" -i               # interativo: agente pergunta cliente + confirma antes de publicar
python -m agents.backlog_decomposer "objetivo aqui"       # decompor objetivo standalone
python -m agents.trace_analyzer                           # KPIs de todas as execuções
python -m contracts.validar                               # valida contratos vs. código
python -m pytest -q                                       # testes (rodam sem API key)
python -m evals.eval_runner                               # impact eval: 8 cenarios x com/sem memoria
python -m evals.eval_runner --max-casos 3 --skip-sem-memoria   # eval rapido
```

CLI não carrega `.env` — exporte as vars ou use Streamlit. Re-rode o seed entre runs (Sentinel fecha o ticket); a CLI já faz auto-reset.

---

## Cenários do seed

| Cliente | Sintoma | Causa esperada |
| --- | --- | --- |
| Acme | Site fora do ar | Deploy ruim — null pointer em `resolveTenant` |
| Beta | Painel lento >10s | Query Mongo sem índice |
| Gama | Pagamentos falhando | Stripe API timeout |
| Delta | Pods reiniciando ~3d | Memory leak (~50MB/h) |
| Echo | Alerta noturno | Falso positivo — Critic deve vetar |
| Foxtrot | Busca intermitente | Rate-limit em cascata |
| Golf | Workers parados | Rotação de secret quebrou auth |
| Hotel | Erro no novo player | Feature flag rampada a 100% |

Botão **Auto-demo** na UI roda os 8 em sequência.

---

## Memória (4 tipos) + Reflection + Impact Eval

Três camadas de memória persistente + uma camada de reflexão automática, plus contextual via embeddings:

| Camada | Onde mora | Conteúdo | Como entra na decisão |
| --- | --- | --- | --- |
| **Longa** | [memory_store/longa/](memory_store/longa/) (8 yamls) | `fatos` (stack, SLOs) + `heuristicas` (hipóteses a validar, não receitas) + `nota_memoria` | Triagem identifica cliente → carrega fatos + heuristicas |
| **Episódica** | [memory_store/episodica/](memory_store/episodica/) (8 yamls) | Incidentes passados resolvidos com `sintoma`/`causa`/`resolucao`/`resumo` | Top-5 episódios do cliente injetados no contexto da investigação |
| **Contextual** | [memory_store/contextual/indice.json](memory_store/contextual/indice.json) | 27 fragmentos com embedding (de longa + episódica) | Busca por similaridade semântica da pergunta — pega fragmentos relevantes mesmo cross-cliente |
| **Reflection** | [reflection_store/licoes/](reflection_store/licoes/) | Lições generalizáveis (políticas que emergiram de incidentes) | Sempre disponíveis (não filtradas por cliente) |

**Embedding adapter** ([agents/embedding_adapter.py](agents/embedding_adapter.py)): usa `text-embedding-3-small` quando `OPENAI_API_KEY` está setada; cai em **fallback determinístico por token-overlap** caso contrário (Sentinel roda em OpenRouter, então o fallback é o caminho default). `python -m agents.embedding_adapter` reconstrói o índice.

**Reflection extractor** ([agents/reflection.py](agents/reflection.py)): após `State.DONE`, dispara em 3 gatilhos — critic vetou / baixa confiança após retry / max_iter sem conclusão. Compõe lição curta a partir do trace, sanitiza secrets, deduplica por assinatura. Política: 1 lição por execução, falha silenciosa (nunca derruba investigação).

**Flags:** `SENTINEL_MEMORY_DISABLED=1` desliga memória; `SENTINEL_REFLECTION_DISABLED=1` desliga extração de lições; `SENTINEL_FORCE_FALLBACK_EMBEDDING=1` força token-overlap mesmo com OpenAI key.

**Impact Eval** ([evals/](evals/)): dataset de 8 cenários ([evals/datasets/sentinel_cases.json](evals/datasets/sentinel_cases.json)). Cada caso roda 2x (com vs sem memória) e mede **11 métricas**, comparativo em `reports/evals/sentinel_impact_report_<ts>.md`:

| Métrica | Threshold | O que mede |
| --- | --- | --- |
| `rca_correctness` | ≥ 0.75 | keywords esperadas presentes na conclusão |
| `forbidden_avoidance` | ≥ 0.90 | ausência de cross-contamination entre cenários |
| `evidence_coverage` | ≥ 0.60 | tipos de evidência mínima presentes |
| `critic_alignment` | ≥ 0.80 | veredito do Critic bate com esperado |
| `degraded_ratio` | ≤ 0.50 | % evidências em fallback (negativa) |
| `retrieval_precision` | ≥ 0.55 | dos fragmentos recuperados, quantos batem (calibrado pra fallback de embedding) |
| `retrieval_recall` | ≥ 0.50 | dos fragmentos esperados, quantos foram recuperados |
| `memory_improvement` | ≥ 0.0 (alvo 0.15) | redução combinada iter+redelegacoes com memória |
| `memory_utilization` | ≥ 0.30 | o RCA usou tokens dos fragmentos recuperados? |
| `hallucination_from_memory` | ≤ 0.45 | tokens da conclusão sem âncora em memória/evidência (negativa) |
| `lesson_quality` | ≥ 0.60 | lições em `reflection_store/licoes/` são informativas? |

**Baseline com LLM + MCPs reais** (1 caso, `acme_deploy_regression`): **11/11 PASS** — `degraded_ratio=0.09`, `retrieval_precision=0.90`, `memory_utilization=1.0`, `hallucination_from_memory=0.19`, `critic_alignment=1.0`. Tempo: ~120s/caso.

**Baseline em modo degradado** (3 casos, sem LLM): 11/11 PASS, `memory_improvement=0.44`.

---

## Diferenciais

**Anti-alucinação (Critic veta se):** <2 evidências · conclusão cita "deploy" sem `tipo=commit` · cita métrica sem `tipo=grafana` · >50% das evidências em fallback `(degradado)` · contradições no sanity LLM. Quando vetado: markdown salvo com ressalvas, Mongo intacto.

**Modo interativo (`-i`):** cliente não identificado → pergunta qual; antes de `registrar_rca` → pede `s/n`. Programático: `run(pergunta, perguntar=..., confirmar=...)`.

**Contract-driven:** edita `.md` → roda `validar` → ajusta código. Cruza `max_etapas` em `rules.md` com `SENTINEL_MAX_ITERATIONS`, `acoes_sensiveis` com `def`s reais, etc. Divergência é factual, não opinião.

**Trace + analyzer:** cada investigação grava `data/traces/trace_<id>.json` (estados, evidências, confiança, redelegações, motivos de veto). `trace_analyzer` agrega: % aprovação, evidências degradadas, motivos de veto mais comuns.

**Handoff produto:** RCA aprovado → `backlog_decomposer` decompõe o fix em `reports/backlog_<id>.md`. Falha do backlog não derruba a investigação.

**Loop ReAct (Reason+Act):** `rca_writer.executar_react(planner=...)` implementa o contrato em [architectures/react/planner.md](../architectures/react/planner.md): cada passo exige `raciocinio` + `criterio_sucesso` antes de escolher `CHAMAR_FERRAMENTA` (`registrar_evidencia` / `finalizar`), `FINALIZAR` ou `PERGUNTAR_USUARIO`. `planner_prompt()` gera o system prompt com schema JSON e as 6 regras de raciocínio (ex: *só FINALIZAR quando todas as evidências foram coletadas*). O loop é testável com planner determinístico — sem dependência de LLM nos testes.

---

## Variáveis

| Var | Default / Efeito |
| --- | --- |
| `OPENROUTER_API_KEY` | **Obrigatória**. Sem ela: degradado. |
| `SENTINEL_MODEL` / `_FAST` | `claude-sonnet-4.5` / `claude-haiku-4.5`. `:free` quebra com MCPs. |
| `MONGO_URI` | `mongodb://localhost:27017/sentinel` |
| `GRAFANA_URL` + `_API_KEY` | Sem ambas: confiança capada em 70%. |
| `GITHUB_PERSONAL_ACCESS_TOKEN` + `SENTINEL_USE_GITHUB=1` + `SENTINEL_GITHUB_REPO` | Ativa GitHub MCP (read-only, só `search_code`). |
| `SENTINEL_MAX_ITERATIONS` | `8` (caminho natural 5 + 3 pro retry) |
| `SENTINEL_OBS_TIMEOUT_S` / `_TECNICO_TIMEOUT_S` | `60` / `90` |
| `SENTINEL_GERAR_BACKLOG` | `1` (decompõe fix após RCA aprovado). `0` desliga. |
| `SENTINEL_MEMORY_DISABLED` | `0` (memória ativa). `1` força no-op — usado pelo impact eval pra baseline. |
| `SENTINEL_REFLECTION_DISABLED` | `0` (extração de lições ativa). `1` desliga reflection após DONE. |
| `OPENAI_API_KEY` | Opcional. Se presente, embedding contextual usa `text-embedding-3-small`. Senão, fallback determinístico por token-overlap. |
| `SENTINEL_FORCE_FALLBACK_EMBEDDING` | `0`. `1` força fallback mesmo com `OPENAI_API_KEY` presente. |

Lista completa: [.env.example](.env.example).

---

## Estrutura

```text
agents/                 8 agentes + memory_adapter + embedding_adapter + reflection + helpers
contracts/              8 × 5 specs + validar.py + analise-agente.md
guards/                 output_guard (PII) + safeguards (max_iter, token budget)
mcp/config.json         5 MCPs (filesystem, mongodb, grafana, playwright, github)
config/                 llm.json + precos.json + diagnosticos.json
data/                   seed_mongo.js + logs/ + traces/
memory_store/
  longa/                8 yamls (fatos + heuristicas por cliente)
  episodica/            8 yamls (incidentes passados resolvidos)
  contextual/           indice.json (embeddings de longa+episodica)
reflection_store/
  licoes/               lições generalizáveis (8 starter + extraídas automaticamente)
evals/                  datasets + suites + eval_runner.py (11 metricas)
app.py                  UI Streamlit
tests/                  testes pytest (rodam sem API key)
reports/                RCAs + backlogs gerados; reports/evals/ recebe relatorios do impact eval
```

---

## Troubleshooting

| Sintoma | Causa / fix |
| --- | --- |
| `ModuleNotFoundError: agents` | `cd` pra raiz do projeto antes de rodar |
| `pymongo.ServerSelectionTimeoutError` | MongoDB não está rodando |
| `streamlit: command not found` | Use `python -m streamlit` |
| `localhost:8501` recusa | Streamlit não subiu/terminal fechou. Rode de novo, aguarde ~5s |
| Confiança 15% + "cliente não encontrado" | Ticket já fechado — re-rode o seed |
| Tudo em 3s + evidências `(degradado: ...)` | `.env` não carregou ou falta `OPENROUTER_API_KEY` |
| Critic veta com "maioria degradado" | Esperado em CLI/testes sem MCPs reais. Use Streamlit |
| Técnico/Obs `(degradado)` mas Critic OK | Modelo `:free` engasga no tool-calling. Use pago |
| Auto-demo trava em VALIDANDO | GitHub MCP buscando SHAs fake. Mantenha `SENTINEL_USE_GITHUB=0` com o seed |
| Sem `backlog_<id>.md` | Critic vetou OU `SENTINEL_GERAR_BACKLOG=0` |
