// Seed do MongoDB para o Multi-Agent Sentinel
// Uso: mongosh "mongodb://localhost:27017/sentinel" data/seed_mongo.js
//
// Cria 4 colecoes com FKs cruzadas para permitir correlacao real:
//   clientes  --< tickets >-- erros >-- rcas
//
// 8 cenarios distintos, cada um exercitando um padrao diferente do Sentinel:
//   1. Acme    -> deploy ruim (null pointer)         -> regressao com RCA historico
//   2. Beta    -> query Mongo lenta (sem deploy)     -> indice ausente
//   3. Gama    -> Stripe timeout (3rd party)         -> dependencia externa
//   4. Delta   -> heap crescente ha 3 dias           -> regressao silenciosa
//   5. Echo    -> alerta espurio (deploy = hotfix)   -> Critic vetando falsa correlacao
//   6. Foxtrot -> rate-limit em cascata              -> falha sistemica multi-servico
//   7. Golf    -> rotacao de secret quebrou auth     -> mudanca de infra fora do codigo
//   8. Hotel   -> feature flag ativada para 100%     -> rollout sem deploy

const db = db.getSiblingDB("sentinel");

["clientes", "tickets", "erros", "rcas"].forEach((c) => db[c].drop());

// ---------- clientes ----------
const acmeId = ObjectId();
const betaId = ObjectId();
const gamaId = ObjectId();
const deltaId = ObjectId();
const echoId = ObjectId();
const foxtrotId = ObjectId();
const golfId = ObjectId();
const hotelId = ObjectId();

db.clientes.insertMany([
  {
    _id: acmeId,
    nome: "Acme Corp",
    plano: "enterprise",
    sla: { resposta_min: 15, resolucao_min: 120 },
    contatos: [{ nome: "João Silva", email: "joao@acme.com", papel: "CTO" }],
    historico_tickets: [],
  },
  {
    _id: betaId,
    nome: "Beta SaaS",
    plano: "pro",
    sla: { resposta_min: 60, resolucao_min: 480 },
    contatos: [{ nome: "Maria Souza", email: "maria@beta.io", papel: "DevOps" }],
    historico_tickets: [],
  },
  {
    _id: gamaId,
    nome: "Gama Logistica",
    plano: "starter",
    sla: { resposta_min: 240, resolucao_min: 1440 },
    contatos: [{ nome: "Carlos Lima", email: "carlos@gama.com.br", papel: "TI" }],
    historico_tickets: [],
  },
  {
    _id: deltaId,
    nome: "Delta Health",
    plano: "enterprise",
    sla: { resposta_min: 15, resolucao_min: 120 },
    contatos: [{ nome: "Ana Pereira", email: "ana@deltahealth.com", papel: "SRE" }],
    historico_tickets: [],
  },
  {
    _id: echoId,
    nome: "Echo Fintech",
    plano: "pro",
    sla: { resposta_min: 30, resolucao_min: 240 },
    contatos: [{ nome: "Pedro Alves", email: "pedro@echofin.io", papel: "Eng Lead" }],
    historico_tickets: [],
  },
  {
    _id: foxtrotId,
    nome: "Foxtrot Marketplace",
    plano: "enterprise",
    sla: { resposta_min: 15, resolucao_min: 120 },
    contatos: [{ nome: "Renata Dias", email: "renata@foxtrot.com", papel: "Head of Eng" }],
    historico_tickets: [],
  },
  {
    _id: golfId,
    nome: "Golf Bank",
    plano: "enterprise",
    sla: { resposta_min: 10, resolucao_min: 60 },
    contatos: [{ nome: "Felipe Couto", email: "felipe@golfbank.com", papel: "Security Lead" }],
    historico_tickets: [],
  },
  {
    _id: hotelId,
    nome: "Hotel Streaming",
    plano: "pro",
    sla: { resposta_min: 30, resolucao_min: 240 },
    contatos: [{ nome: "Larissa Mota", email: "larissa@hotelstream.tv", papel: "Product Eng" }],
    historico_tickets: [],
  },
]);

// ---------- erros ----------
const erroAcmeId = ObjectId();
const erroBetaId = ObjectId();
const erroGamaId = ObjectId();
const erroDeltaId = ObjectId();
const erroEchoId = ObjectId();
const erroFoxtrotId = ObjectId();
const erroGolfId = ObjectId();
const erroHotelId = ObjectId();
const erroAntigoId = ObjectId();

const commitRuim = "a1b2c3d4e5f6";       // Acme: deploy quebrado
const commitAntigo = "9988776655aa";     // Acme: incidente historico ja resolvido
const commitEcho = "7766554433ee";       // Echo: deploy que parece suspeito mas e hotfix
const commitDelta = "5544332211dd";      // Delta: ultimo deploy, ha 4 dias
const commitHotel = "ccddeeff0011";      // Hotel: deploy que introduziu a feature flag (1 semana atras)

db.erros.insertMany([
  // 1. Acme: null pointer apos deploy
  {
    _id: erroAcmeId,
    tipo: "HTTP_500",
    stacktrace:
      "TypeError: Cannot read properties of undefined (reading 'tenantId')\n  at resolveTenant (src/auth/tenant.ts:42)\n  at Middleware.run (src/server.ts:118)",
    frequencia: 1432,
    primeiro_ocorrido: ISODate("2026-05-05T14:28:11Z"),
    ultimo_ocorrido: ISODate("2026-05-05T14:35:02Z"),
    deploy_id: "dpl_2026_05_05_1428",
    commit_sha: commitRuim,
    grafana_alert_id: "alert_cpu_spike_97",
    ticket_relacionado: null,
  },
  // 2. Beta: query lenta, sem deploy correlato
  {
    _id: erroBetaId,
    tipo: "TIMEOUT_DB",
    stacktrace:
      "MongoServerSelectionError: connection timed out after 30000ms\n  at Topology.selectServer (mongodb/lib/sdam/topology.js:303)\n  query: db.audit_logs.find({org: ObjectId(...), data: {$gte: ...}}).sort({data: -1})",
    frequencia: 87,
    primeiro_ocorrido: ISODate("2026-05-04T22:10:00Z"),
    ultimo_ocorrido: ISODate("2026-05-06T14:18:42Z"),
    deploy_id: null,
    commit_sha: null,
    grafana_alert_id: "alert_db_p99_3000ms",
    ticket_relacionado: null,
  },
  // 3. Gama: Stripe timeout (terceiro)
  {
    _id: erroGamaId,
    tipo: "EXTERNAL_API_TIMEOUT",
    stacktrace:
      "StripeConnectionError: Request to Stripe API timed out\n  at PaymentService.charge (src/payments/stripe.ts:67)\n  upstream_status: 503\n  upstream_host: api.stripe.com",
    frequencia: 412,
    primeiro_ocorrido: ISODate("2026-05-06T13:45:00Z"),
    ultimo_ocorrido: ISODate("2026-05-06T14:50:00Z"),
    deploy_id: null,
    commit_sha: null,
    grafana_alert_id: "alert_payment_failure_rate",
    ticket_relacionado: null,
  },
  // 4. Delta: memory leak, sintoma silencioso e gradual
  {
    _id: erroDeltaId,
    tipo: "OOM_KILLED",
    stacktrace:
      "Process killed by oom-killer after heap grew to 3.8GB (limit 4GB)\n  pod: api-delta-7f9d4c-xq2pl\n  uptime_at_kill: 71h22m\n  observed: gradual rss growth ~50MB/h since 2026-05-03",
    frequencia: 4,
    primeiro_ocorrido: ISODate("2026-05-03T18:00:00Z"),
    ultimo_ocorrido: ISODate("2026-05-06T14:00:00Z"),
    deploy_id: "dpl_2026_05_02_1100",
    commit_sha: commitDelta,
    grafana_alert_id: "alert_heap_growth_delta",
    ticket_relacionado: null,
  },
  // 5. Echo: ruido, parece bug mas era hotfix
  {
    _id: erroEchoId,
    tipo: "HTTP_502",
    stacktrace:
      "BadGateway: upstream connection reset\n  during rolling restart of payment-worker\n  duration: 47s\n  recovered_at: 2026-05-06T03:14:00Z",
    frequencia: 23,
    primeiro_ocorrido: ISODate("2026-05-06T03:13:13Z"),
    ultimo_ocorrido: ISODate("2026-05-06T03:14:00Z"),
    deploy_id: "dpl_2026_05_06_0312",
    commit_sha: commitEcho,
    grafana_alert_id: "alert_5xx_burst_echo",
    ticket_relacionado: null,
  },
  // 6. Foxtrot: rate-limit em cascata entre servicos internos
  {
    _id: erroFoxtrotId,
    tipo: "RATE_LIMIT_EXCEEDED",
    stacktrace:
      "TooManyRequests: 429 from internal-svc/catalog\n  at HttpClient.request (src/http/client.ts:88)\n  at SearchService.enrich (src/search/service.ts:201)\n  observed: catalog-svc esta saturado por chamadas do recommender-svc apos pico de trafego\n  cascata: search -> recommender -> catalog -> users",
    frequencia: 2890,
    primeiro_ocorrido: ISODate("2026-05-06T11:20:00Z"),
    ultimo_ocorrido: ISODate("2026-05-06T14:55:00Z"),
    deploy_id: null,
    commit_sha: null,
    grafana_alert_id: "alert_429_burst_foxtrot",
    ticket_relacionado: null,
  },
  // 7. Golf: rotacao de secret quebrou auth do worker
  {
    _id: erroGolfId,
    tipo: "AUTH_FAILED",
    stacktrace:
      "UnauthorizedError: invalid client credentials\n  at OAuthClient.fetchToken (src/auth/oauth.ts:54)\n  at LedgerWorker.start (src/workers/ledger.ts:19)\n  context: secret AWS Secrets Manager 'ledger-oauth' rotacionado em 2026-05-06T02:00:00Z\n  pods continuam usando credencial antiga em memoria — sem deploy desde 2026-04-28",
    frequencia: 1740,
    primeiro_ocorrido: ISODate("2026-05-06T02:01:00Z"),
    ultimo_ocorrido: ISODate("2026-05-06T14:50:00Z"),
    deploy_id: null,
    commit_sha: null,
    grafana_alert_id: "alert_auth_fail_golf",
    ticket_relacionado: null,
  },
  // 8. Hotel: feature flag rampada para 100% causou erro escondido
  {
    _id: erroHotelId,
    tipo: "HTTP_500",
    stacktrace:
      "AssertionError: expected user.subscription to be defined\n  at NewPlayer.render (src/player/new.tsx:74)\n  feature_flag: 'new_player_v2' = 100% (era 5% ate 2026-05-06T10:00:00Z)\n  ultimo deploy de codigo: 2026-04-29 (commit ccddeeff0011 introduziu a flag)",
    frequencia: 638,
    primeiro_ocorrido: ISODate("2026-05-06T10:02:00Z"),
    ultimo_ocorrido: ISODate("2026-05-06T14:45:00Z"),
    deploy_id: null,
    commit_sha: commitHotel,
    grafana_alert_id: "alert_player_500_hotel",
    ticket_relacionado: null,
  },
  // 9. Acme: incidente historico (ja resolvido)
  {
    _id: erroAntigoId,
    tipo: "HTTP_500",
    stacktrace:
      "TypeError: Cannot read properties of undefined (reading 'tenantId')\n  at resolveTenant (src/auth/tenant.ts:38)",
    frequencia: 312,
    primeiro_ocorrido: ISODate("2026-03-12T09:00:00Z"),
    ultimo_ocorrido: ISODate("2026-03-12T11:30:00Z"),
    deploy_id: "dpl_2026_03_12_0855",
    commit_sha: commitAntigo,
    grafana_alert_id: "alert_cpu_spike_91",
    ticket_relacionado: null,
  },
]);

// ---------- tickets ----------
const ticketAcmeId = ObjectId();
const ticketBetaId = ObjectId();
const ticketGamaId = ObjectId();
const ticketDeltaId = ObjectId();
const ticketEchoId = ObjectId();
const ticketFoxtrotId = ObjectId();
const ticketGolfId = ObjectId();
const ticketHotelId = ObjectId();
const ticketAntigoId = ObjectId();

db.tickets.insertMany([
  {
    _id: ticketAcmeId,
    clientId: acmeId,
    descricao: "Site do João (Acme) está fora do ar — erro 500 ao logar",
    status: "aberto",
    prioridade: "P1",
    erros_correlacionados: [erroAcmeId],
    deploy_suspeito: commitRuim,
    url: "https://httpstat.us/500",
    log_path: "data/logs/acme.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-05T14:32:00Z"),
    atualizado_em: ISODate("2026-05-05T14:32:00Z"),
  },
  {
    _id: ticketBetaId,
    clientId: betaId,
    descricao: "Lentidão intermitente no painel administrativo (carregamento >10s)",
    status: "aberto",
    prioridade: "P2",
    erros_correlacionados: [erroBetaId],
    deploy_suspeito: null,
    url: "https://httpstat.us/200?sleep=12000",
    log_path: "data/logs/beta.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-04T22:15:00Z"),
    atualizado_em: ISODate("2026-05-06T14:00:00Z"),
  },
  {
    _id: ticketGamaId,
    clientId: gamaId,
    descricao: "Pagamentos falhando — clientes não conseguem finalizar checkout",
    status: "aberto",
    prioridade: "P1",
    erros_correlacionados: [erroGamaId],
    deploy_suspeito: null,
    url: "https://httpstat.us/504",
    log_path: "data/logs/gama.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-06T13:50:00Z"),
    atualizado_em: ISODate("2026-05-06T14:55:00Z"),
  },
  {
    _id: ticketDeltaId,
    clientId: deltaId,
    descricao: "Pods da API Delta reiniciando a cada ~3 dias — usuários sentem latência momentânea",
    status: "aberto",
    prioridade: "P2",
    erros_correlacionados: [erroDeltaId],
    deploy_suspeito: null,
    url: "https://httpstat.us/500",
    log_path: "data/logs/delta.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-06T08:00:00Z"),
    atualizado_em: ISODate("2026-05-06T14:00:00Z"),
  },
  {
    _id: ticketEchoId,
    clientId: echoId,
    descricao: "Alerta disparou na madrugada — clientes reclamam mas sistema parece OK agora",
    status: "aberto",
    prioridade: "P3",
    erros_correlacionados: [erroEchoId],
    deploy_suspeito: commitEcho,
    url: "https://httpstat.us/200",
    log_path: "data/logs/echo.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-06T08:30:00Z"),
    atualizado_em: ISODate("2026-05-06T08:30:00Z"),
  },
  {
    _id: ticketFoxtrotId,
    clientId: foxtrotId,
    descricao: "Busca e recomendacoes do marketplace caindo intermitentemente nas ultimas 3h",
    status: "aberto",
    prioridade: "P1",
    erros_correlacionados: [erroFoxtrotId],
    deploy_suspeito: null,
    url: "https://httpstat.us/429",
    log_path: "data/logs/foxtrot.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-06T11:30:00Z"),
    atualizado_em: ISODate("2026-05-06T14:55:00Z"),
  },
  {
    _id: ticketGolfId,
    clientId: golfId,
    descricao: "Workers de conciliacao parados desde a madrugada — fila acumulando",
    status: "aberto",
    prioridade: "P1",
    erros_correlacionados: [erroGolfId],
    deploy_suspeito: null,
    url: "https://httpstat.us/401",
    log_path: "data/logs/golf.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-06T07:00:00Z"),
    atualizado_em: ISODate("2026-05-06T14:50:00Z"),
  },
  {
    _id: ticketHotelId,
    clientId: hotelId,
    descricao: "Player novo dando tela branca para usuarios free desde manha",
    status: "aberto",
    prioridade: "P2",
    erros_correlacionados: [erroHotelId],
    deploy_suspeito: null,
    url: "https://httpstat.us/500",
    log_path: "data/logs/hotel.log",
    rca_gerado_id: null,
    criado_em: ISODate("2026-05-06T10:30:00Z"),
    atualizado_em: ISODate("2026-05-06T14:45:00Z"),
  },
  {
    _id: ticketAntigoId,
    clientId: acmeId,
    descricao: "Erro 500 esporádico em /login (resolvido)",
    status: "fechado",
    prioridade: "P1",
    erros_correlacionados: [erroAntigoId],
    deploy_suspeito: commitAntigo,
    rca_gerado_id: null,
    criado_em: ISODate("2026-03-12T09:05:00Z"),
    atualizado_em: ISODate("2026-03-12T12:00:00Z"),
  },
]);

// fecha o ciclo de FK: erro -> ticket
db.erros.updateOne({ _id: erroAcmeId }, { $set: { ticket_relacionado: ticketAcmeId } });
db.erros.updateOne({ _id: erroBetaId }, { $set: { ticket_relacionado: ticketBetaId } });
db.erros.updateOne({ _id: erroGamaId }, { $set: { ticket_relacionado: ticketGamaId } });
db.erros.updateOne({ _id: erroDeltaId }, { $set: { ticket_relacionado: ticketDeltaId } });
db.erros.updateOne({ _id: erroEchoId }, { $set: { ticket_relacionado: ticketEchoId } });
db.erros.updateOne({ _id: erroFoxtrotId }, { $set: { ticket_relacionado: ticketFoxtrotId } });
db.erros.updateOne({ _id: erroGolfId }, { $set: { ticket_relacionado: ticketGolfId } });
db.erros.updateOne({ _id: erroHotelId }, { $set: { ticket_relacionado: ticketHotelId } });
db.erros.updateOne({ _id: erroAntigoId }, { $set: { ticket_relacionado: ticketAntigoId } });

db.clientes.updateOne({ _id: acmeId }, { $set: { historico_tickets: [ticketAntigoId, ticketAcmeId] } });
db.clientes.updateOne({ _id: betaId }, { $set: { historico_tickets: [ticketBetaId] } });
db.clientes.updateOne({ _id: gamaId }, { $set: { historico_tickets: [ticketGamaId] } });
db.clientes.updateOne({ _id: deltaId }, { $set: { historico_tickets: [ticketDeltaId] } });
db.clientes.updateOne({ _id: echoId }, { $set: { historico_tickets: [ticketEchoId] } });
db.clientes.updateOne({ _id: foxtrotId }, { $set: { historico_tickets: [ticketFoxtrotId] } });
db.clientes.updateOne({ _id: golfId }, { $set: { historico_tickets: [ticketGolfId] } });
db.clientes.updateOne({ _id: hotelId }, { $set: { historico_tickets: [ticketHotelId] } });

// ---------- rcas historicos ----------
// Acme: bug que ja foi resolvido (Critic deve referenciar isso na nova investigacao)
const rcaAntigoId = ObjectId();
db.rcas.insertOne({
  _id: rcaAntigoId,
  ticket_id: ticketAntigoId,
  evidencias: [
    { tipo: "commit", ref: commitAntigo, nota: "introduziu acesso a tenantId sem null-check" },
    { tipo: "grafana", ref: "alert_cpu_spike_91", nota: "spike CPU coincidente com deploy" },
  ],
  conclusao:
    "Deploy " +
    commitAntigo +
    " introduziu null-pointer em resolveTenant. Rollback aplicado às 11:30. Hotfix em PR #214.",
  gerado_em: ISODate("2026-03-12T12:00:00Z"),
});
db.tickets.updateOne({ _id: ticketAntigoId }, { $set: { rca_gerado_id: rcaAntigoId } });

// Echo: RCA historico mostra que o commit "suspeito" foi um HOTFIX de bug critico,
// nao um deploy ruim. O Critic deve usar isso para vetar conclusao de "deploy quebrou".
const rcaEchoHistoricoId = ObjectId();
db.rcas.insertOne({
  _id: rcaEchoHistoricoId,
  ticket_id: null,
  evidencias: [
    { tipo: "commit", ref: commitEcho, nota: "hotfix: corrige race condition em payment-worker (PR #87, urgente)" },
    { tipo: "github_pr", ref: "PR#87", nota: "merged 2026-05-06T03:00:00Z apos incidente P1 anterior" },
  ],
  conclusao:
    "Deploy " +
    commitEcho +
    " foi um HOTFIX de race condition. Rolling restart causou 502s transientes por 47s — comportamento esperado, nao regressao.",
  gerado_em: ISODate("2026-05-06T03:30:00Z"),
});

// ---------- indices para correlacao rapida ----------
db.tickets.createIndex({ clientId: 1, status: 1 });
db.tickets.createIndex({ deploy_suspeito: 1 });
db.erros.createIndex({ commit_sha: 1 });
db.erros.createIndex({ stacktrace: "text" });
db.rcas.createIndex({ ticket_id: 1 });

print("seed: " + db.clientes.countDocuments() + " clientes, " +
      db.tickets.countDocuments() + " tickets, " +
      db.erros.countDocuments() + " erros, " +
      db.rcas.countDocuments() + " rcas");
