# S0 & S1 Plan — Detailed Tasks and Acceptance Criteria

Companion documents: `docs/project/ROADMAP.md` (stage overview),
`docs/project/TEAM_WORK_PLAN.md` (owners + statuses),
spec §6.3 (security), §9.4 (RBAC), §10.6 (required-evidence matrix), §17.2–17.3
(planning + GO/NO-GO gates), §18.2 (acceptance criteria).

Status vocabulary: 📋 planned → 🔶 implemented (not executed) → ✅ executed/tested.

---

# S0 — Grounding and environment (GO/NO-GO G0)

## S0.1 — Environment verification 🔶

**Owner:** Mohamed Amine Gotai (G0 is a lab task), assisted by Bilel for the check script.

Tasks:
1. ✅/🔶 Run `scripts/check-environment.ps1`: verifies Docker Engine (CLI **and**
   daemon), WSL2, Kind, kubectl, Git, Python ≥ 3.11, free RAM/disk; prints a
   GO/NO-GO per item.
   - **Recorded status at repo initialization (2026-11-02):**
     - Docker Desktop CLI 29.3.1 present, **Docker Engine daemon NOT running**
       (named pipe `dockerDesktopLinuxEngine` absent).
     - WSL2 installed (Ubuntu + `docker-desktop` distros, stopped).
     - **Kind NOT installed.**
     - kubectl client v1.34.1 present; git 2.55.0; Python 3.14.7 (≥ 3.11 required
       by MCP SDK v2 — OK, spec §4.4).
     - Hardware: 15.2 GB RAM, 12 logical CPUs, 671 GB free disk → adequate for a
       Kind single-node lab (free RAM at check time was low, 2.7 GB — close
       memory-heavy apps before cluster work).
2. 🔶 Start Docker Desktop manually (user action — no automatic install/start is
   performed by this repository) and re-run the check until all items print GO.
3. 🔶 Install **Kind** manually (user action — no automatic installation is
   performed by this repository). Verified pin targets (checked against the
   official kind v0.33.0 release notes on 2026-11-02):
   - `kind` CLI version **v0.33.0**;
   - node image **`kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5`**
     (already pinned in `k8s/kind-config.yaml`; the release notes require the
     `@sha256` digest to guarantee an image built for this release);
   - `kind load docker-image` requires the SAME kind release that created the
     cluster — install v0.33.0 before creating the cluster.
4. 🔶 Upgrade **kubectl** if needed: the pinned server is 1.37.0, so the supported
   client range is **1.36–1.38** (Kubernetes skew policy, kubectl ± 1 minor).
   The client observed at initialization (v1.34.1) is below the window; the
   operator upgrades it manually. `check-environment.ps1` warns on too-old
   clients.

**Acceptance criteria (AC-S0.1):**
- [✅ rule defined / 🔶 run pending] `check-environment.ps1` run prints GO for:
  Docker daemon reachable, `kind version` works, `kubectl version` client in the
  1.36–1.38 window (with a printed warning otherwise),
  Python ≥ 3.11, ≥ 8 GB free RAM at cluster time, ≥ 20 GB free disk.
- Versions of Docker / Kind / kubectl / kind node image recorded in
  `docs/project/TEAM_WORK_PLAN.md` once all GO.
- **No** automatic installation happened — installs are explicit human actions.

## S0.2 — Literature matrix (spec §2.2) 📋

**Owner:** Bilel Amri.

Tasks: build `docs/research/LITERATURE_MATRIX.md` covering R14–R21
(K8sGPT, HolmesGPT, Botkube, ARGUS, Cloud-OpsBench, TriFleetRCA, R2Act, K8sGPT
abstention benchmark): full-text reading of each, publication status, licence,
repository/dataset availability, what OpsPilot may claim or must not claim.

**Acceptance criteria:** matrix exists with one row per reference; each repository
or dataset link verified reachable or explicitly marked unavailable; no claim of
invention or superiority copied from marketing pages; wording follows the
"authorised formulation" rule (spec §2.2).

## S0.3 — Supervisor agreement (Annex A) 📋

**Owner:** both. Send Annex A questions (50-question threshold, fine-tuning
optionality, subject validation, Kind-based demo, MCP SDK v2, 3 vs 6 scenarios) and
record answers in `docs/project/DECISION_LOG.md` (created with the first entry).

**Acceptance criteria:** each Annex A question has a status
(open / answered / deferred) and, when answered, the date + medium of the answer.

## S0.4 — Repository foundation 🔶 (done in the initialization commit)

Tasks: all documentation (`README`, `TEAM`, `CONTRIBUTING`, architecture, roadmap,
this plan, team work plan, traceability), spec copy in `docs/specification/`,
`.gitignore` + `.env.example`, fresh git init on `main`, remote connected, initial
push. Plus the *pre-S1 preparation items assigned in S0* (see below): Kind config,
RBAC, all three scenario manifests (SC-01/SC-02/SC-04), demo app, scripts, basic tests.

**Acceptance criteria (AC-S0.4):**
- [✅] `python -m pytest tests/ -v` passes locally (tests need no cluster).
- [✅] `git log --oneline` shows a single clean initialization commit;
      push to `origin/main` succeeded without force.
- [✅] No secrets in the tree (`git grep` for API-key patterns clean);
      `.env` ignored, `.env.example` present.

---

# S1 — Kubernetes laboratory (first real snapshot, gate G1)

## S1.1 — Cluster + namespace + read-only RBAC 🔶

**Owner:** Mohamed Amine Gotai.

Tasks:
1. 🔶 `scripts/create-cluster.ps1` runs `kind create cluster --config
   k8s/kind-config.yaml` (cluster name `opspilot`, namespace-scoped node config),
   then applies `k8s/rbac/namespace.yaml`, `serviceaccount.yaml`, `role.yaml`,
   `rolebinding.yaml`.
2. 🔶 Verify the RBAC refusals (spec §9.4 + AC-04):
   ```powershell
   kubectl auth can-i --as=system:serviceaccount:opspilot-lab:opspilot-mcp \
     get pods -n opspilot-lab                  # expect yes
   kubectl auth can-i --as=system:serviceaccount:opspilot-lab:opspilot-mcp \
     get pods/log -n opspilot-lab              # expect yes
   kubectl auth can-i --as=system:serviceaccount:opspilot-lab:opspilot-mcp \
     list events -n opspilot-lab               # expect yes
   kubectl auth can-i --as=system:serviceaccount:opspilot-lab:opspilot-mcp \
     create pods -n opspilot-lab               # expect no
   kubectl auth can-i --as=system:serviceaccount:opspilot-lab:opspilot-mcp \
     delete pods -n opspilot-lab               # expect no
   kubectl auth can-i --as=system:serviceaccount:opspilot-lab:opspilot-mcp \
     get secrets -n opspilot-lab               # expect no
   kubectl auth can-i --as=system:serviceaccount:opspilot-lab:opspilot-mcp \
     patch deployments -n opspilot-lab         # expect no

   ```
3. 🔶 Record `kubectl version --output` + `kind version` + node image tag in the
   work plan table (version freezing after first success).

**Acceptance criteria (AC-S1.1 / AC-01 partial):**
- `kubectl get ns opspilot-lab` succeeds on a cluster created by the script;
  all seven `can-i` expectations match; the granted verbs match exactly the Role
  rules (no extra verbs); securities SEC-01/SEC-02 verifiably hold.

## S1.2 — Demo application image 🔶

**Owner:** Mohamed Amine Gotai.

Tasks: 🔶 `scripts/build-load-demo-image.ps1`: `docker build -t
opspilot/demo-app:s1 demo-app` then `kind load docker-image opspilot/demo-app:s1
--name opspilot`. The app (`demo-app/app.py`) is a **small FastAPI application**
(spec §17.2 S1 row) with scenario behaviors selected via the `SCENARIO` env var:
`healthy` (serves `/healthz`, `/info`), `crashloop` (logs then exits non-zero →
CrashLoopBackOff), `oom` (allocates memory beyond the container limit →
OOMKilled, exit code 137). **This app is the incident generator only — the project
backend (S5) is a separate FastAPI service that does not exist yet.**

**Acceptance criteria (AC-S1.2):**
- `kubectl run selftest --image=opspilot/demo-app:s1 --image-pull-policy=Never`
  (or a healthy deployment) reaches `Running`;
  `curl <pod-ip>:8080/healthz` returns 200 from inside the cluster
  (`kubectl exec` is used **only by the human operator**, it is not an OpsPilot
  capability — SEC / §9.4).
- Image tag recorded; no third-party beyond FastAPI+uvicorn pinned in
  `demo-app/requirements.txt` (frozen at first successful build).

## S1.3 — Scenario SC-01 CrashLoopBackOff 🔶

**Owner:** Mohamed Amine Gotai.

Tasks: 🔶 `scripts/run-scenario.ps1 -Scenario SC-01` applies
`scenarios/sc-01-crashloopbackoff/deployment.yaml` (element env `SCENARIO=crashloop`),
waits, and prints pod status/events/logs evidence so the operator can observe:
Pod phase **Running** (restartPolicy keeps it alive) while container state is
`Waiting` with reason **CrashLoopBackOff** and growing `restartCount`
(spec §9.3 distinction — a key S1 learning artifact). The container logs its
attempt number each start so `--previous` logs differ from current logs.

**Acceptance criteria (AC-S1.3 / AC-02 partial):**
- `kubectl get pod -o json` shows `status.containerStatuses[0].state.waiting.reason
  == "CrashLoopBackOff"` with `restartCount >= 3` within ~3 minutes;
- `status.phase == "Running"` is expected and must be documented as proof that Pod
  phase ≠ container state;
- `kubectl logs --previous` returns the crashed instance's logs (Kubernetes
  retains them — if unavailable, record the limitation, spec §9.2 FR-04);
- a collection with `collect-manual-evidence.ps1` produced
  `out/evidence/SC-01/*.json` = **first validated real snapshot (G1 exit)**.

## S1.4 — Scenario SC-02 ImagePullBackOff 🔶

**Owner:** Mohamed Amine Gotai.

Tasks: 🔶 run `-Scenario SC-02`: the manifest points at an image whose registry
host uses the reserved `.invalid` TLD (RFC 2606) with `imagePullPolicy: Always`
→ the kubelet genuinely **attempts** pulls, the host can never resolve, the
first event is `ErrImagePull`, and after the first retry the Pod cycles
`ImagePullBackOff` — no real registry identity is contacted. Design correction
(S0 review): an earlier draft used `imagePullPolicy: Never` with a never-built
tag, which yields `ErrImageNeverPull` (no pull attempt) and is NOT the target
failure family; the corrected design is documented in the manifest header, and
a network variant (nonexistent tag on a real registry) is noted as alternative.

**Acceptance criteria:** pod events include `Failed`/`ErrImagePull` and
`ImagePullBackOff` referencing the Pod UID; `ErrImageNeverPull` must NOT appear
(pull-attempt design guard); no application logs exist (container
never started — absence expected, per spec §10.6 row 2); events carry
firstTimestamp/lastTimestamp/count (spec §9.2).

## S1.5 — Scenario SC-04 OOMKilled 🔶

**Owner:** Mohamed Amine Gotai.

Tasks: 🔶 run `-Scenario SC-04`: deployment sets `resources.limits.memory: 64Mi`
and env `SCENARIO=oom`; the app allocates memory well above the limit → kernel
kills the container → `lastState.terminated.reason == "OOMKilled"`,
`exitCode: 137`, restart loop. Note **exit code 137 must be *observed*, not
assumed** (spec §10.6 row 3).

**Acceptance criteria:** `lastState.terminated.reason == "OOMKilled"`,
`exitCode == 137` observed from a real run; spec limits/requests read from
`spec.containers[0].resources` match the manifest; `restartCount` grows.

## S1.6 — Manual evidence collection script 🔶

**Owner:** Mohamed Amine Gotai (structure reviewed by Bilel — it previews the S3
evidence schema: identity, timestamps, source, payload hash).

Tasks: 🔶 `scripts/collect-manual-evidence.ps1 -Scenario SC-01` writes per
scenario into `out/evidence/<SC>/`:
- `pod_status.json` — full `kubectl get pod -o json`;
- `logs_current.json` / `logs_previous.json` — `kubectl logs [--previous]` with
  captured metadata (pod name + **pod UID**, container, collected_at ISO-8601 UTC,
  current/previous flag, tail bound) or an explicit `unavailable` record with the
  reason (never invent data — NFR-01);
- `events.json` — filtered by `involvedObject.uid`;
- `snapshot_manifest.json` — scenario id, cluster version, collection timestamps,
  sha256 of each payload file (prefigures `snapshot_id`/`payload_hash`, spec §10.3).

**Acceptance criteria:** all files parse as JSON; every evidence record contains
source, identity (pod UID), collection time and hash; missing data recorded as
`{status: unavailable, reason: ...}`; the snapshot manifest hashes match the files.

## S1.7 — Basic validation tests 🔶

**Owner:** Bilel Amri. ✅ `tests/` runs **without any cluster**:
- `tests/test_yaml_validity.py` — every committed YAML parses; expected keys present.
- `tests/test_rbac_manifests.py` — Role grants exactly the allowed verbs and
  **never** touches `secrets`, never a write verb (static guarantee of SEC-02
  before the cluster exists).
- `tests/test_scenario_contracts.py` — each `scenario.yaml` declare id, family,
  expected observations per spec §10.6 matrix, and the deployment file it points to
  exists with the expected behavior env/tags.

**Acceptance criteria:** `python -m pytest tests/ -v` green with no network.

---

# S0/S1 hard blockers & rules recap

- **No automatic installation** of Docker/Kind: the operator runs both manually;
  the repo ships only check + creation scripts.
- Do **not** mark S1 ✅ until G0 passes and a real snapshot exists in `out/evidence/`.
- The (S1-prepared) cluster/RBAC apply step lives in `create-cluster.ps1` but RBAC
  *refusal testing* is re-run in S2 when MCP starts calling with this identity.
- SC-03 remains reserved as the **optional** conditioning extension (Pending Pod,
  spec §4.3), owned by S2 and executed only when the MVP is stable and the team
  confirms it; mandatory families are SC-01/SC-02/SC-04, executed in S1
  (see ROADMAP stage-ownership note).
