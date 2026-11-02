# OpsPilot Roadmap — S0 to S7

Adapted from spec §17.2 (8-week indicative plan) and §17.3 (GO/NO-GO gates).
**Status vocabulary:** 📋 *planned* → 🔶 *implemented (not yet executed)* → ✅ *tested/executed*.
Nothing is marked ✅ without a recorded run.

| Stage | Objective | Key tasks | Milestone / exit criterion | Status |
|---|---|---|---|---|
| **S0** — Grounding & environment | Validate scope + environment; prepare research context | Targeted literature matrix (verify publication status, licences, dataset availability per spec §2.2); supervisor agreement on scope (Annex A questions); verify Docker Engine, Kind, RAM/disk; freeze tool versions after *first successful run* | **G0**: Docker engine + Kind functional on the student machine | 🔶 configs + `check-environment.ps1` committed; **G0 OPEN** — Docker Engine was not running and Kind was not installed at repo initialization |
| **S1** — Kubernetes laboratory | First reproducible real incident | Kind cluster + namespace + read-only RBAC; FastAPI demo app image; **execution of the three mandatory scenarios: SC-01 CrashLoopBackOff, SC-02 ImagePullBackOff, SC-04 OOMKilled** (manifests prepared in S0); manual collection of status/logs(`previous`)/events; scripts for run/reset | **G1**: at least one scenario generates real, reproducible proofs (all three observed and snapshot-validated) | 🔶 manifests, demo app, scripts committed; execution blocked on G0 |
| **S2** — Extend lab + MCP | Secured collection channel | The 4 MCP tools with bounded parameters; RBAC refusal tests via `kubectl auth can-i` **refusal suite**; frozen snapshots; **optional SC-03 Pending Pod** only if the MVP is stable AND the team confirms the extension (spec §4.3) | **G2**: MCP tools answer with real data AND RBAC refuses mutations/secrets | 📋 planned |
| **S3** — Evidence schema + EQG | The research core | Normalize proofs (schema §10.3); provenance fields; completeness/freshness/consistency/provenance rules with IDs + positive & negative tests per rule (§16.4); decision policy + priority (§10.5); degraded-case fixtures (12 conditions) | **G3**: EQG unit-tested, deterministic, explainable on complete and degraded cases | 📋 planned |
| **S4** — RAG pipeline | Versioned, cite-able corpus | Corpus manifest (1.36 + 1.37, CC-BY-4.0 attribution); ingestion pipeline (§8.3); lexical index; embeddings choice + pgvector; hybrid + reranking experiment repo | **G4**: corpus ingested, retrieval and citations functionally verified | 📋 planned |
| **S5** — AI workflow + UI | End-to-end investigation | LangGraph single graph; LLM selection after feasibility test (JSON-structured output); structured report model (§11.3); **post-generation validator** (§10.7) ; FastAPI API (§13.3); base React UI screens (§13.1) | Complete incident path reproducible via UI | 📋 planned |
| **S6 — Benchmarking** | Measure EQG effect | ≥ 50-question RAG dataset (35 dev / 15 holdout), qrels double-annotated; retrieval configs R1–R4 (Recall@k, Precision@k, MRR, nDCG@k, latency); generation metrics (§12.1); EQG benchmark (§12.2: false-pass, false-block, per-dimension P/R/F1); end-to-end D1/D2/D3 (§12.3); version-filter ON/OFF experiment | Preliminary results recorded with sample sizes, models/config versions | 📋 planned |
| **S7 — Finalization** | Ship deliverables | Security tests consolidation (§16.1); error analysis (false-pass/false-block documenteds); technical report (D2); demo script (D3); README/video support revision (D1/D4); honest limits section (§19.1) | Deliverables submitted; complete, reproducible, mastered demonstration | 📋 planned |

**Scenario numbering and stage ownership — mandatory vs optional** (spec §4.1, §4.3, §10.6):

- **Mandatory MVP families (owned and executed in S1): SC-01 CrashLoopBackOff,
  SC-02 ImagePullBackOff, SC-04 OOMKilled.** Their manifests and scenario
  contracts are prepared during S0 (part of the repository foundation) so S1
  can immediately generate and observe real incidents once G0 passes; validation
  happens in S1 and the resulting snapshots feed S3.
- **SC-03 (optional): Pending Pod.** Reserved by numbering and owned by S2, to be
  executed only if the MVP is stable and the team confirms the conditional
  extension (spec §4.3, together with missing-ConfigMap and readiness-probe
  variants; a readiness failure must never be presented as equivalent to a
  liveness failure). SC-03 is not a mandatory deliverable — see the deviation
  note below.
- Numbering keeps SC-01 → SC-02 → (SC-03 optional) → SC-04 so file names stay
  stable whether or not the extension is ever built.

**Documented deviation from spec §17.2 phase detail (to confirm with the
supervisor, Annex A):** the specification's indicative plan lists "SC-02, SC-03"
inside S2. This repository consolidates the execution of all three MANDATORY
families into S1 (spec §4.1 requires them in the MVP; §20.5 requires a validated
incident before EQG/RAG start), and keeps S2 for the MCP/RBAC channel plus the
OPTIONAL SC-03. This matches our team work plan; flag it in the next supervisor
sync.

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
