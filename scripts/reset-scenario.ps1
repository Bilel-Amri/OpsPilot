# OpsPilot S1 — remove a scenario deployment and its pods (lab reset only).
# Usage: ./scripts/reset-scenario.ps1 -Scenario SC-01  (| SC-02 | SC-04)
# This is a human lab action, not an OpsPilot capability (spec §15.3).

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('SC-01', 'SC-02', 'SC-04', 'ALL')]
    [string]$Scenario
)

$ErrorActionPreference = 'Continue'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$labPath  = Join-Path $RepoRoot 'out\evidence'

if ($Scenario -eq 'ALL') {
    kubectl delete deployment --all -n opspilot-lab --ignore-not-found
} else {
    kubectl delete deployment -n opspilot-lab -l opspilot.io/scenario=$Scenario --ignore-not-found
}
if ($LASTEXITCODE -ne 0) { Write-Warning 'kubectl delete returned an error — inspect kubectl get pods -n opspilot-lab for leftovers.' }

# Delete orphaned pods only if they are terminally stuck in Terminating/Terminated
# and belong to the lab; normal deletion with the deployment should suffice.
kubectl wait --for=delete pod -n opspilot-lab -l opspilot.io/scenario=SC-01 --timeout=60s 2>$null | Out-Null
kubectl wait --for=delete pod -n opspilot-lab -l opspilot.io/scenario=SC-02 --timeout=60s 2>$null | Out-Null
kubectl wait --for=delete pod -n opspilot-lab -l opspilot.io/scenario=SC-04 --timeout=60s 2>$null | Out-Null
Write-Output 'Remaining lab pods:'
kubectl get pods -n opspilot-lab -o wide

Write-Output ''
Write-Output 'Snapshot artifacts under out/evidence are preserved (git-ignored). Delete manually if you want a clean slate:'
Write-Output ("  Remove-Item -Recurse -Force '{0}'" -f $labPath)
