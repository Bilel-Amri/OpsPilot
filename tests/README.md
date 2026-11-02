# Tests

Basic validation suite for the S0/S1 repository foundation. Everything here runs
**without a cluster and without network access** (spec §16.4: no implicit network
calls in unit tests). Cluster-level validations (RBAC `auth can-i`, scenario
generation, image build) are executed by `scripts/*.ps1` and documented in
`docs/project/S0_S1_PLAN.md`.

| File | Covers | Status |
|---|---|---|
| `test_yaml_validity.py` | Kind config structure + pinned node image; all committed YAML parses; demo app is not the backend and supports the 3 scenarios | ✅ tests executed locally |
| `test_rbac_manifests.py` | Role grants exactly `pods get,list` / `pods/log get` / `events get,list`; never secrets, never write verbs; RoleBinding scoped to the lab namespace | ✅ tests executed locally (runtime refusals verified by script at G0) |
| `test_scenario_contracts.py` | The 3 mandatory scenarios (SC-01/SC-02/SC-04) exist with contract + deployment; SC-02 stays offline-reproducible; SC-04 forbids presuming exit code 137; workloads target `opspilot-lab` | ✅ tests executed locally (real incident generation still pending G1) |

Run:

```powershell
python -m pytest tests/ -v
```

Later suites (per stage): schema tests (S3), MCP integration (S2, requires cluster),
RBAC runtime (`kubectl auth can-i`), RAG ingestion/retrieval (S4), workflow (S5),
non-regression frozen set (§16.1).
