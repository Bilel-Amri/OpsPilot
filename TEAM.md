# Team & Collaboration

**OpsPilot — TEK-UP University — AI Engineering**

Team members (per specification §17.1 — primary responsibilities; both members are
expected to understand the shared architecture and cross-review each other's code):

| Member | Primary responsibility | Expected individual deliverables |
|---|---|---|
| **Bilel Amri** | RAG, document management & versioning, evidence schemas, EQG, LLM/LangChain/LangGraph integration, benchmark protocol & research evaluation | Corpus manifest; RAG ingestion/retrieval; EQG rules + EQG tests; RAG benchmark report; experimental analysis |
| **Mohamed Amine Gotai** | Kubernetes laboratory, incident scenarios, MCP server & RBAC, React frontend, API integration & CI/CD | Cluster configs; reproducible scenarios; MCP tools; RBAC refusal tests; frontend; CI workflow |
| **Both** | Shared architecture & end-to-end integration; testing; evidence annotation (double annotation + documented disagreements); research report; final demonstration | Cross-reviews (each student reviews the other's PRs); validated test sets; joint report; mastered demo |

Validation note (spec §17.1): this split is a proposal to be **confirmed by both
students**. Confirm by commenting on the PR that implements this table or by editing
it in a follow-up commit.

## Current stage (S0/S1)

- S0/S1 groundwork (cluster/RBAC configs, scenarios, demo app, scripts, docs) was
  drafted together and committed as the repository initialization commit **by
  Bilel Amri**; it is the shared foundation, not one member's deliverable.
- Next: **Mohamed Amine** leads G0 (Docker Engine + Kind validation) and S1 real
  snapshot validation; **Bilel** finalizes S0 literature matrix and prepares S3 EQG
  skeletons after G1.

## Collaboration rules

1. **Branches & PRs — every change through a PR.** No direct pushes to `main`
   (except the single initialization commit). See `CONTRIBUTING.md`.
2. **Cross-review:** each member reviews the other's pull requests. Either member
   may request changes; disagreements are resolved in a short call and documented
   in the PR conversation.
3. **Shared architecture decisions** (schemas, EQG decision policy, API routes,
   report format) are discussed *before* implementation; the decision is recorded
   in the PR description or `docs/project/REQUIREMENTS_TRACEABILITY.md` notes.
4. **Honest status vocabulary** everywhere: a feature is *planned*, *implemented*,
   or *tested/executed* — never claim "works" before it executes.
5. **Secrets & data hygiene:** no API keys, tokens or kubeconfigs in the repo
   (SEC-07). The lab contains only synthetic test data (NFR-08).
6. **The authoritative spec is `Cahier_des_charges_OpsPilot.pdf`** (copy in
   `docs/specification/`). The PDF is never modified; deviations are proposed
   through issues/PRs named `spec-change: ...` and confirmed by the supervisor.
7. **Meeting cadence:** at least one sync per study week during S0–S7; each sync
   ends with an updated status in `docs/project/TEAM_WORK_PLAN.md`.
8. **Annotations & qrels (S6):** both members annotate independently, then compare;
   disagreements are adjudicated and documented in the evaluation dataset README.
