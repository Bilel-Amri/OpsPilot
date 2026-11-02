# Contributing to OpsPilot

Thanks for contributing. OpsPilot is a two-student research prototype: keep changes
small, reproducible and honestly tested.

## Git workflow

1. `main` is **always runnable**: it may lag behind features but never contains
   broken files or secrets.
2. Work on **feature branches** named after the roadmap stage and task:
   - `s0/g0-environment-check`
   - `s1/sc01-crashloop-scenario`
   - `s2/mcp-list-pods`
   - `s3/eqg-freshness-rule`
   - format: `s<stage>/<short-slug>` (lowercase, hyphens).
3. Open a **pull request into `main`** for every change. The **other team member
   reviews** (spec §16.2: each student reviews the other's contributions).
4. Merge with a **squash merge** (or fast-forward) so `main` history contains one
   clean commit per PR; never force-push.
5. CI (when wired in S2) must pass: lint, targeted type checks, pytest unit tests,
   JSON/YAML validation, integration tests that require no secrets.

## Commits

Use **Conventional Commits** prefixes:

| Prefix | Use |
|---|---|
| `feat:` | new functionality (a scenario, an EQG rule, an MCP tool…) |
| `fix:` | bug fix |
| `docs:` | documentation |
| `test:` | tests only |
| `refactor:` | code change that is neither feat nor fix |
| `chore:` | tooling, configs, housekeeping |

Subject: imperative, ≤ ~50 chars, e.g. `feat(scenarios): add SC-04 OOMKilled manifest`.
Add a body when the *why* is not obvious. Reference roadmap items (`S1`, `S3.2`)
or issues in the body.

## Pull request checklist

- [ ] PR describes **what** and **why**; decisions documented.
- [ ] Status correctly labeled *implemented* or *tested* — no "works" claim without
      an executed run (paste command + output excerpt for runtime features).
- [ ] No secrets, tokens, kubeconfigs or real clusters' data.
- [ ] New/changed YAML validated (`python -m pytest tests/ -v` passes, or the change
      is a test).
- [ ] Docs updated when the change affects architecture, roadmap status or the
      team work plan table.
- [ ] At least **one cross-review approval** (both members for EQG/evaluation
      changes that affect the research protocol).

## Coding conventions

- **Python** (backend, EQG, eval): PEP 8, type hints on all interfaces and data
  models (spec §16.4), explicit exceptions documented, plain pytest — no implicit
  network calls in unit tests.
- **YAML** manifests: one file per object where practical, `metadata.labels` include
  `app.kubernetes.io/name` and `app.kubernetes.io/part-of: opspilot`.
- **PowerShell** scripts: `#!/usr/bin/env pwsh`-style header comment, parameterized
  (`-Scenario`), fail fast (`$ErrorActionPreference = 'Stop'`), print the exact
  failing step — never mask errors (NFR-01).
- **Frontend** (S5+): TypeScript strict mode; loading / error / empty states on
  every screen (spec §13.2).

## Attribution requirements (for the future corpus)

Any re-used text from official Kubernetes documentation must keep, in the corpus
manifest: source URL, version, collection date, content hash and the
**CC-BY-4.0** license text/attribution (spec §8.1). Public postmortems are cited as
bibliographic links only — never redistributed without a verified license.

## Reporting problems

Open a GitHub issue with: roadmap stage, exact command run, expected vs actual
output, environment versions (`scripts/check-environment.ps1` output). For spec
deviations label the issue `spec-change`.
