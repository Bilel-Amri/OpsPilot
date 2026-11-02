# Requirements Traceability — Course Requirements → Modules → Tests → Demonstration

Source: spec §18.3 (course requirements) + §6.1/§6.2 (functional/non-functional
requirements) + §18.2 (acceptance criteria AC-01…AC-11). The five university
requirements below are the teachable course objectives; the delivery deliverables
(GitHub repo, report, demonstration, presentation) are tracked at the end.

Status per row reflects the *repository state*, not aspirational completion:
🔶 = implemented (not executed) · ✅ tested/executed · 📋 planned (stage in
`docs/project/ROADMAP.md`) · nothing is claimed as proven before it runs.

---

## R1 — Document management / RAG

> Course requirement: versioned document management, metadata, update process, citations.

| Aspect | Where in this repository | Where implemented (stage) | Test / proof | Demonstration | Status |
|---|---|---|---|---|---|
| Versioned corpus (1.36 + 1.37) with manifest (URL, version, date, hash, licence) | planned `backend/app/rag/`, corpus manifest file | S4 | manifest schema validation; content-hash change detection test | "Base documentaire" screen lists documents by version with status | 📋 |
| Metadata model (spec §8.4: document_id, chunk_id, section, source URL, licence…) | planned `backend/app/rag/` | S4 | JSON schema tests for document/chunk records | Corpus screen: section + version + URL per chunk | 📋 |
| Update process (re-index only changed pages) | planned ingestion pipeline | S4 | re-index test with a mutated page hash | Re-ingestion demo preserving version | 📋 |
| Citations with minimum identifiers (chunk, doc, section, version, URL) | planned report validator (S5) | S4/S5 | validator rejects citations without required fields | Report panel shows D-refs resolvable to real passages | 📋 |
| Licence compliance CC-BY-4.0 attribution | `CONTRIBUTING.md` (Attribution section) | S4 | review checklist item | Attribution shown in corpus screen footer | 📋 |

**Evidence already present:** CONTRIBUTING attribution rules; architecture §7
(RAG design); FR-09/FR-10 mapping below.

## R2 — Tool Calling / MCP

> Course requirement: an MCP server exposing tools that are *actually executed*
> (spec §9.1 — presence of a schema file is NOT sufficient).

| Aspect | Where | Where implemented | Test / proof | Demonstration | Status |
|---|---|---|---|---|---|
| 4 read-only tools: `list_pods`, `get_pod_status`, `get_pod_logs`, `get_recent_events` (contracts per spec §9.2) | planned `mcp_server/` | S2 | MCP integration test: real `tools/list` + `tools/call` against the Kind cluster (AC-03) | Live incident collection during demo | 📋 |
| Real cluster outputs (FR-02..FR-05) | planned | S2 | output freshness: real Pod UID / resourceVersion from the lab cluster | UI reveals the tool calls and collected data (§13.2) | 📋 |
| Pod phase vs container state distinction (spec §9.3) | planned tool output contract | S2 | fixture: pod with phase Running + container waiting CrashLoopBackOff parsed correctly | Report distinguishes them explicitly | 📋 |
| Input validation, bounds, timeouts (SEC-05) | planned tool layer | S2 | unit tests: oversize `tail_lines`, wrong namespace rejected | Error surfaces shown in UI | 📋 |
| RBAC enforcement behind tools (SEC-01/02) | 🔶 `k8s/rbac/*` + planned refusal suite | S0/S2 | `kubectl auth can-i` 7-line matrix (`docs/project/S0_S1_PLAN.md` §S1.1) + static tests `tests/test_rbac_manifests.py` | Run the can-i matrix live in demo | 🔶 |

**Evidence already present:** RBAC manifests + static security tests; Kind config;
evidence-collection scripts previewing tool outputs at S1 (manual substitute:
`scripts/collect-manual-evidence.ps1`).

## R3 — LangChain and/or LangGraph

> Course requirement: LangChain for RAG components; LangGraph for the investigation
> workflow (one graph, explicit state — spec §11.2; no complex multi-agent).

| Aspect | Where | Where implemented | Test / proof | Demonstration | Status |
|---|---|---|---|---|---|
| LangChain: loaders/splitters/embeddings/retrievers in the document pipeline | planned `backend/app/rag/` | S4 | retrieval unit tests with fixture documents | Corpus + retrieval panel during incident investigation | 📋 |
| LangGraph: single investigation graph with EQG-driven branching (spec §11.1) | planned `backend/app/workflow/` | S5 | workflow tests: EQG partial → tentative-only report; MCP outage → explicit failure state, no fabricated data (§11.4) | Trace of graph steps shown in UI | 📋 |
| MCP client invoked *by the workflow* (spec §9.1) | planned workflow node | S5 | integration: contains recorded tool call ids per investigation | Demo shows tool calls per run | 📋 |
| Framework versions frozen (LangChain / LangGraph / MCP SDK v2, Python ≥ 3.11) | planned `backend/requirements.txt` + lockfile | S4/S5 | dependency freeze recorded per NFR-02 | Versions panel / README badges of record | 📋 |

**Evidence already present:** specification-derived workflow data flow
(`docs/architecture/ARCHITECTURE.md` §3 — the graph is designed before coding,
spec §11.1 order preserved).

## R4 — Retrieval benchmark

> Course requirement: comparable retrieval configurations evaluated with qrels.

| Aspect | Where | Where implemented | Test / proof | Demonstration | Status |
|---|---|---|---|---|---|
| Configurations R1 lexical (PostgreSQL `ts_rank`/`ts_rank_cd` — **never named BM25**, spec §12.1), R2 dense (pgvector), R3 hybrid, R4 hybrid+reranker | planned `evaluation/rag/retrieval/` | S4 (configs) / S6 (runs) | metric computation unit tests on hand-computed fixtures | Benchmark screen comparing configurations | 📋 |
| Dataset ≥ 50 questions, 35 dev / 15 holdout, version-sensitivity flagged (spec §12.1) | planned `evaluation/datasets/rag/` | S6 | qrels review record (dual annotation + documented disagreements) | Holdout metrics reported with sample sizes | 📋 |
| Metrics Recall@k, Precision@k, MRR, nDCG@k, retrieval latency p50/p95 | planned evaluation runner | S6 | fixture with known ranking → exact expected values | Metric tables per configuration | 📋 |
| Version-filter ON/OFF experiment on version-sensitive questions (H4) | planned | S6 | question list marked version-sensitive with inspection notes | Comparison table + negative results reported | 📋 |

## R5 — Generation benchmark

> Course requirement: reference answers, groundedness, citation evaluation.

| Aspect | Where | Where implemented | Test / proof | Demonstration | Status |
|---|---|---|---|---|---|
| Reference answers + expected content elements per question | planned `evaluation/datasets/rag/generation/` | S6 | dual annotation record | Side-by-side reference vs generated answer | 📋 |
| Generation metrics: answer correctness, faithfulness/groundedness, citation accuracy, completeness, documentation-abstention (spec §12.1) | planned | S6 | scorer unit tests on labeled examples | Metric table per configuration | 📋 |
| Diagnostics end-to-end comparison D1 evidence-only / D2 +RAG / D3 +EQG with frozen model+prompt+context budget (spec §12.3) | planned | S6 | run manifest records model/prompt/version/params (NFR-02) | Unsupported-diagnosis-rate vs coverage table; **explicit reporting of cases where EQG is harmful** (spec §19.1) | 📋 |

## Cross-cutting: EQG (the research contribution, S3) and web interface (S5)

| Aspect | Where | Stage | Test / proof | Demonstration | Status |
|---|---|---|---|---|---|
| Evidence schema with provenance fields (FR-06, spec §10.3) | planned `backend/app/evidence/` | S3 | JSON-schema validation tests; unknown stays null | Evidence panel with provenance | 📋 |
| EQG deterministic rules with IDs + positive/negative tests (FR-07, §16.4) | planned `backend/app/eqg/` | S3 | per-rule unit tests; 12-case degraded matrix (AC-06: confusion matrix per dimension) | EQG decision + triggered rules shown | 📋 |
| Confirmation block on blocked diagnoses (FR-08, SEC-06) | planned post-generation validator | S5 | negative test: LLM outputs "confirmed" while EQG=CONFLICTED → report rejected | Demo deliberately shows a blocked confirmation | 📋 |
| React web UI: incident / evidence & EQG / diagnostic / benchmark / corpus screens (FR-14, AC-10, §13.1) | planned `frontend/` | S5 | e2e path test; loading/error/empty states per screen | Live complete path | 📋 |
| No remediation capability (SEC-08, §15.3) | static + RBAC | S0+ | static tests assert no write verbs; can-i matrix | Operator explains refusals live | 🔶 |

## Course deliverables (spec §18.1)

| Deliverable | Contents | Repository anchor | Status |
|---|---|---|---|
| D1 GitHub repository | documented code, README, architecture, instructions, tests, CI, progressive commit history | root of this repo; CI workflow planned S2 | 🔶 (CI pending) |
| D2 Technical report | problem, state of the art, design, data, EQG, RAG, MCP, security, methodology, results, limits | planned `report/` (S7) | 📋 |
| D3 Demonstration | controlled incident, real collection, EQG decision, document retrieval, evidenced report | scripted path derived from `scripts/*.ps1` + UI (S5) | 📋 |
| D4 Presentation | business objective, RQ, architecture, experimentation, results, limits | planned `report/` (S7) | 📋 |

## FR/NFR full mapping (spec §6)

| Req | Meaning | Module | Test/Demo | Status |
|---|---|---|---|---|
| FR-01 | create/read incidents | S5 API | API test + UI history | 📋 |
| FR-02 | list pods (namespace) | S2 MCP | integration test, real output | 📋 |
| FR-03 | pod status detail | S2 MCP | schema test, phases distinguished | 📋 |
| FR-04 | logs current/previous | S2 MCP | previous logs available when retained (or explicit limit note §9.2) | 📋 |
| FR-05 | linked events | S2 MCP | events bound to object UID + window | 📋 |
| FR-06 | normalize observations to evidence | S3 evidence schema | JSON Schema tests | 📋 |
| FR-07 | EQG 4 dimensions | S3 EQG | explainable reproducible decision | 📋 |
| FR-08 | block unauthorized confirmed diagnosis | S5 validator | negative test of LLM output | 📋 |
| FR-09 | ingest versioned docs | S4 RAG | indexed + manifested corpus | 📋 |
| FR-10 | retrieve & rank passages | S4 RAG | qrels-based metrics | 📋 |
| FR-11 | D and E citations shown separately | S5 report + UI | distinct Dxxx/Exxx in report schema | 📋 |
| FR-12 | run LangGraph workflow | S5 workflow | step tracing + error handling | 📋 |
| FR-13 | persist snapshots/decisions/results | S4/S5 PostgreSQL | consultable history | 📋 |
| FR-14 | UI for incidents & evidence | S5 frontend | full path demonstrable | 📋 |
| FR-15 | run RAG/EQG/diagnostic evaluations | S6 runner | reproducible reports | 📋 |
| NFR-01 | errors explicitly surfaced, never neutralized | everywhere (`unavailable` records at S1; §11.4 table at S5) | unit tests; demo shows an explicit failure | 🔶 (convention defined; enforced by `collect-manual-evidence.ps1` contract) |
| NFR-02 | reproducibility (versions, prompts, params) | run manifests S4–S6 | run config recorded | 📋 |
| NFR-03 | security — restrictive RBAC | 🔶 `k8s/rbac/` | can-i matrix | 🔶 |
| NFR-04 | traceability | evidence schema S3 + audit trail S5 | join incident→snapshot→tools→evidence→docs | 📋 |
| NFR-05 | maintainability (typing, modularity, tests) | all code | pytest + targeted type checks in CI (S2) | 🔶 (tests exist; CI wiring in S2) |
| NFR-06 | portability (verified instructions, versioned configs) | scripts + docs | quick start executed step-by-step | 🔶 (pending execution) |
| NFR-07 | per-step latency measurement | S5 instrumentation + S6 | latency table (no production SLA claimed) | 📋 |
| NFR-08 | confidentiality | lab is synthetic; redaction policy | no production data in repo (verified `.gitignore` + review) | 🔶 |
| NFR-09 | accessible UI states | S5 frontend | e2e states test | 📋 |

## Acceptance criteria coverage (spec §18.2 → stage)

AC-01 → S1 (S1-01..03) · AC-02 → S1 (S1-06..08) · AC-03 → S2 · AC-04 → S0/S2
(can-i matrix) · AC-05 → S3 · AC-06 → S3 · AC-07 → S4 · AC-08 → S6 ·
AC-09 → S5 · AC-10 → S5 · AC-11 → S7 (report review against §19.1 wording rules).
