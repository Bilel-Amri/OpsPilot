# OpsPilot Roadmap — S0 to S7

Adapted from spec §17.2 (8-week indicative plan) and §17.3 (GO/NO-GO gates).
**Status vocabulary:** 📋 *planned* → 🔶 *implemented (not yet executed)* → ✅ *tested/executed*.
Nothing is marked ✅ without a recorded run.

| Stage | Objective | Key tasks | Milestone / exit criterion | Status |
|---|---|---|---|---|
| **S0** — Grounding & environment | Validate scope + environment; prepare research context | Targeted literature matrix (verify publication status, licences, dataset availability per spec §2.2); supervisor agreement on scope (Annex A questions); verify Docker Engine, Kind, RAM/disk; freeze tool versions after *first successful run* | **G0**: Docker engine + Kind functional on the student machine | 🔶 configs + `check-environment.ps1` committed; **G0 OPEN** — Docker Engine was not running and Kind was not installed at repo initialization |
| **S1** — Kubernetes laboratory | First reproducible real incident | Kind cluster + namespace + read-only RBAC; FastAPI demo app image; **SC-01 CrashLoopBackOff**; manual collection of status/logs(`previous`)/events; scripts for run/reset | **G1**: a scenario generates real, reproducible proofs (first snapshot validated) | 🔶 manifests, demo app, scripts committed; execution blocked on G0 |
| **S2** — Extend lab + MCP | Secured collection channel | **SC-02 ImagePullBackOff**, **SC-03** (reserved, see note); the 4 MCP tools with bounded parameters; RBAC refusal tests via `kubectl auth can-i` (`kubectl auth can-i` **refusal suite**); frozen snapshots | **G2**: MCP tools answer with real data AND RBAC refuses mutations/secrets | 📋 planned (SC-02 + SC-04 manifests already prepared in S0 per task assignment, execution deferred to S2) |
| **S3** — Evidence schema + EQG | The research core | Normalize proofs (schema §10.3); provenance fields; completeness/freshness/consistency/provenance rules with IDs + positive & negative tests per rule (§16.4); decision policy + priority (§10.5); degraded-case fixtures (12 conditions) | **G3**: EQG unit-tested, deterministic, explainable on complete and degraded cases | 📋 planned |
| **S4** — RAG pipeline | Versioned, cite-able corpus | Corpus manifest (1.36 + 1.37, CC-BY-4.0 attribution); ingestion pipeline (§8.3); lexical index; embeddings choice + pgvector; hybrid + reranking experiment repo | **G4**: corpus ingested, retrieval and citations functionally verified | 📋 planned |
| **S5** — AI workflow + UI | End-to-end investigation | LangGraph single graph; LLM selection after feasibility test (JSON-structured output); structured report model (§11.3); **post-generation validator** (§10.7) ; FastAPI API (§13.3); base React UI screens (§13.1) | Complete incident path reproducible via UI | 📋 planned |
| **S6 — Benchmarking** | Measure EQG effect | ≥ 50-question RAG dataset (35 dev / 15 holdout), qrels double-annotated; retrieval configs R1–R4 (Recall@k, Precision@k, MRR, nDCG@k, latency); generation metrics (§12.1); EQG benchmark (§12.2: false-pass, false-block, per-dimension P/R/F1); end-to-end D1/D2/D3 (§12.3); version-filter ON/OFF experiment | Preliminary results recorded with sample sizes, models/config versions | 📋 planned |
| **S7 — Finalization** | Ship deliverables | Security tests consolidation (§16.1); error analysis (false-pass/false-block documenteds); technical report (D2); demo script (D3); README/video support revision (D1/D4); honest limits section (§19.1) | Deliverables submitted; complete, reproducible, mastered demonstration | 📋 planned |

**Conditional extensions** (spec §4.3, only if the MVP is stable and team confirms):
SC-03 **Pending Pod**, missing ConfigMap, readiness-probe failure (never presented as
equivalent to a liveness failure). The scenario numbering in this repository keeps
**SC-03 reserved** for the conditional "Pending Pod" family and numbers the mandatory
OOMKilled scenario **SC-04**, matching the assignment in the team work plan
(3 mandatory families: CrashLoopBackOff, ImagePullBackOff, OOMKilled — spec §4.1).

**Gates recap** (spec §17.3) with the action-if-failed:

- **G0** env: if Docker/Kind cannot run → reduce local load or use an authorized
  alternative environment; no EQG/RAG development start.
- **G1** real incident: if not reproducible → fix scenario/collector before EQG.
- **G2** MCP secured: if RBAC not verified → **no LLM integration at all**.
- **G3** EQG testable → clarify rules/ground truth before S6.
- **G4** RAG measurable → reduce corpus or fix metadata/chunking.
- **G5** demonstration → prioritize stability and honest limits over extensions.

**Anti-scope rules** (justified by spec): no automatic remediation ever; no Secret
reads; no fine-tuning in MVP (optional, pending supervisor confirmation, R23/Annex A);
no multi-agent architecture; no new frameworks beyond §20 unless justified and validated.
