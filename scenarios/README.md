# OpsPilot incident scenarios — specification directory
#
# Three mandatory MVP incident families (spec §4.1):
#   SC-01  CrashLoopBackOff
#   SC-02  ImagePullBackOff
#   SC-04  OOMKilled
#
# Numbering note (also in docs/project/ROADMAP.md): SC-03 is intentionally
# RESERVED for the OPTIONAL extension family "Pending Pod" (spec §4.3). It is
# NOT a mandatory deliverable: the three mandatory MVP families are SC-01, SC-02
# and SC-04 (spec §4.1), whose manifests are prepared in S0 and executed in S1.
# SC-03 is owned by S2 and may only be implemented after MVP validation and team
# confirmation (together with the other conditional extensions).
#
# Each scenario folder contains:
#   deployment.yaml  - the manifest that creates the incident (via demo-app image)
#   scenario.yaml    - the contract: id, family, expected observations and
#                      which absence is critical (spec §10.6 matrix). This file
#                      is the predecessor of the S3 EQG per-scenario rules and of
#                      the S6 degraded-case fixtures.
#
# Generation is human-triggered only (`scripts/run-scenario.ps1`), consistent
# with the no-remediation boundary (spec §15.3): the MVP itself never mutates
# the cluster; these manifests exist solely to *create laboratory incidents*.
#
# Observed facts must NEVER be fabricated from these expectations: scenario.yaml
# describes what a HEALTHY collection should contain, not what any run will
# return (NFR-01).
