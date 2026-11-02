# Team Work Plan — Who Implements What, Where, and What Happens Next

Statuses: 📋 planned · 🔶 **implemented (not executed yet)** · ✅ executed/tested · ⛔ blocked (with reason).
Update this table at every team sync (TEAM.md rule 7). Owners follow spec §17.1.

Current repo state (initialization commit, 2026-11-02): S0/S1 groundwork 🔶.
**Blocker ⛔ G0:** Docker Engine daemon not running + Kind not installed at check
time — both require **manual** action by the operator; nothing was installed
automatically. See `scripts/check-environment.ps1` run log in
`docs/project/S0_S1_PLAN.md` §S0.1.

## Stage-independent / shared tasks

| ID | Task | Owner | Files | Expected result | Depends on | Status |
|---|---|---|---|---|---|---|
| SH-01 | Repository foundation: docs, .gitignore, .env.example, git init, first push | Bilel (drafted) — both validate | `README.md`,`TEAM.md`,`CONTRIBUTING.md`,`docs/**`,`.gitignore`,`.env.example` | Clean, documented repo on GitHub, single init commit | — | ✅ (uncommitted until push completes; verify after CI wiring in S2) |
| SH-02 | Manifest/`scenario.yaml` format definition (precursor of S3 evidence contracts) | Bilel, reviewed by M. Amine | `scenarios/*/scenario.yaml`, `tests/test_scenario_contracts.py` | Stable convention for per-scenario expected observations (spec §10.6) | — | 🔶 |
| SH-03 | G0 environment validation (Docker Desktop start, Kind install, check re-run) | Mohamed Amine | — (machine-level) + recorded versions in this table | All-GO output of `check-environment.ps1`; Docker/Kind/kubectl versions frozen | Docker Engine | ⛔ blocked: manual operator action required |
| SH-04 | Supervisor agreement on Annex A | Both | `docs/project/DECISION_LOG.md` (created at first entry) | Each Annex A question answered/deferred with date | — | 📋 |

## S0 — environment & grounding

| ID | Task | Owner | Files | Expected result | Depends on | Status |
|---|---|---|---|---|---|---|
| S0-01 | `check-environment.ps1` (engine/daemon, WSL2, Kind, kubectl, python, RAM/disk) | Mohamed Amine | `scripts/check-environment.ps1` | Prints per-item GO/NO-GO, exits non-zero on NO-GO | — | 🔶 (script ✅ syntax-reviewed; no NO-GO-free run yet) |
| S0-02 | Literature matrix R14–R21 with licence/repo verification | Bilel | `docs/research/LITERATURE_MATRIX.md` | One verified row per reference; allowed-claims column | SH-04 optional | 📋 |
| S0-03 | Kind cluster config + version pinning policy | Mohamed Amine | `k8s/kind-config.yaml` | Reproducible single-node cluster; kind v0.33.0 + node image digest-pinned `kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5` (verified from official kind v0.33.0 release notes, 2026-11-02) | — | 🔶 (pin verified vs release notes; cluster creation not run) |
| S0-04 | Read-only RBAC manifests | Mohamed Amine | `k8s/rbac/{namespace,serviceaccount,role,rolebinding}.yaml` | SA `opspilot-mcp` limited to `pods get,list` / `pods/log get` / `events get,list`; static tests green | S0-01 (for apply) | 🔶 apply pending |
| S0-05 | Basic test suite (YAML validity, RBAC static security, scenario contracts) | Bilel | `tests/*.py` | `pytest` green, no cluster/no network required | — | ✅ |
| S0-06 | Spec copy + readable extraction in `docs/specification/` | Bilel | `docs/specification/*` | Authoritative PDF preserved untouched + extraction marked unofficial | — | ✅ |

## S1 — laboratory (first real snapshot = gate G1)

| ID | Task | Owner | Files | Expected result | Depends on | Status |
|---|---|---|---|---|---|---|
| S1-01 | `create-cluster.ps1` (kind create + apply RBAC + verify) | Mohamed Amine | `scripts/create-cluster.ps1` | Cluster `opspilot` up; namespace+RBAC applied; script fails loudly on any step | SH-03 | 🔶 |
| S1-02 | Demo FastAPI app (healthy / crashloop / oom behaviors) | Mohamed Amine | `demo-app/{app.py,requirements.txt,Dockerfile}` | One image, three behaviors by env var; **not** the future backend | Docker Engine | 🔶 |
| S1-03 | `build-load-demo-image.ps1` | Mohamed Amine | `scripts/build-load-demo-image.ps1` | Image `opspilot/demo-app:s1` built + loaded into Kind | S1-01, S1-02 | 🔶 |
| S1-04 | Scenario manifests SC-01/SC-02/SC-04 + scenario contracts | Mohamed Amine, Bilel reviews | `scenarios/sc-01-crashloopbackoff/*`, `scenarios/sc-02-imagepullbackoff/*`, `scenarios/sc-04-oomkilled/*` | Declarative, reproducible incidents (SC-02: `imagePullPolicy: Always` + unresolvable `.invalid` host → genuine pull attempts → ErrImagePull/ImagePullBackOff; a `Never` policy would yield ErrImageNeverPull and was corrected after the S0 review) | S1-03 | 🔶 |
| S1-05 | `run-scenario.ps1` + `reset-scenario.ps1` | Mohamed Amine | `scripts/run-scenario.ps1`, `scripts/reset-scenario.ps1` | Deploys/waits/prints evidence or removes cleanly; reset restores healthy lab | S1-03 | 🔶 |
| S1-06 | **SC-01 real run → first snapshot (G1)** | Mohamed Amine, Bilel reviews snapshot | — | Waiting reason CrashLoopBackOff + restartCount with Pod phase Running documented; records in `out/evidence/SC-01/` | S1-05 | ⛔ (G0) |
| S1-07 | **SC-02 real run** (`ErrImagePull`/`ImagePullBackOff` events; no container logs expected) | Mohamed Amine | — | Events with timestamps + involvedObject UID collected | S1-05 | ⛔ (G0) |
| S1-08 | **SC-04 real run** (`OOMKilled` + exit code **observed** as 137, spec limits read from pod spec) | Mohamed Amine | — | lastState.terminated OOMKilled evidence | S1-05 | ⛔ (G0) |
| S1-09 | `collect-manual-evidence.ps1` (status + logs current/previous + events + snapshot manifest with hashes) | Mohamed Amine, structure pre-reviewed by Bilel | `scripts/collect-manual-evidence.ps1` | JSON files with identity/timestamps/hash; missing data = explicit `unavailable` records | S1-05 | 🔶 |
| S1-10 | Freeze real versions in docs (after first success) | Both | this file + `docs/architecture/ARCHITECTURE.md` §5 | Docker/Kind/kubectl/node image/demo image versions recorded | S1-06..08 | 📋 |

**S1 completion path (strictly ordered):** SH-03 → S1-01 → S1-03 → S1-05 →
S1-06 → S1-09 → update this table → open the S2 planning PR.

## After S1 (defined here so each student can start scoped work; implementation happens in its stage)

| Stage | Bilel Amri (files) | Mohamed Amine Gotai (files) |
|---|---|---|
| S2 | MCP client smoke-tests supporting workflow integration; consumer-side tool contract tests `tests/test_mcp_contracts.py` | `mcp_server/` (4 tools, bounded params §9.2, SDK v2); `kubectl auth can-i` refusal suite; **optional** SC-03 execution (only if the MVP-stable extension is confirmed, ROADMAP note); frozen snapshots |
| S3 | `backend/app/evidence/` schema + `backend/app/eqg/` rules (each rule: id + rationale + positive & negative test, §16.4); degraded-case fixture generator (12 conditions, parent snapshots) | Lab-side fixes surfaced by EQG tests; scenario tag/label support for snapshot lineage |
| S4 | `backend/app/rag/` corpus manifest (1.36/1.37, CC-BY-4.0), ingestion, lexical+dense+hybrid retrievers | Postgres container/dev compose integration; `kubectl`-side helpers for lab metadata |
| S5 | LangGraph graph + prompt + post-generation validator + report schema | `backend/` FastAPI API routes (§13.3); `frontend/` React screens (§13.1); CI workflow (lint/pytest/YAML) |
| S6 | Benchmark datasets + runners + qrels double-annotation (both annotate), D1/D2/D3 runs | Evaluation dashboard screens; run artifacts storage conventions |
| S7 | Error analysis + technical report sections | Security test consolidation + demo video + release tags |

Cross-review pairing (CONTRIBUTING): Bilel reviews lab/MCP/frontend/CI PRs;
Mohamed Amine reviews evidence/EQG/RAG/evaluation PRs; EQG-vs-lab contract changes
(SH-02) need both.

## Versions log (fill after first successful execution — G0/G1)

| Tool | Version | Recorded by | Date |
|---|---|---|---|
| Docker Engine | — (not running at init) | — | 2026-11-02 |
| Docker CLI | 29.3.1 | Bilel | 2026-11-02 |
| Kind | — (not installed at init; target release **v0.33.0** per release notes) | — | 2026-11-02 |
| kubectl | v1.34.1 (client) — **below the skew window** for the pinned 1.37.0 node; operator must upgrade to 1.36–1.38 manually | Bilel | 2026-11-02 |
| Python | 3.14.7 | Bilel | 2026-11-02 |
| Kind node image | `kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5` — digest verified against the official kind v0.33.0 release notes (not yet pulled/ran) | Bilel | 2026-11-02 |
| demo-app image | — candidate `opspilot/demo-app:s1` | — | — |
