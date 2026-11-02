# OpsPilot S1 — trigger a controlled incident scenario and show the resulting evidence.
# Usage: ./scripts/run-scenario.ps1 -Scenario SC-01   (| SC-02 | SC-04)
# Human-triggered only: OpsPilot itself never mutates the cluster (spec §15.3).

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('SC-01', 'SC-02', 'SC-04')]
    [string]$Scenario
)

$ErrorActionPreference = 'Stop'

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$Deployment = Switch ($Scenario) {
    'SC-01' { Join-Path $RepoRoot 'scenarios\sc-01-crashloopbackoff\deployment.yaml' }
    'SC-02' { Join-Path $RepoRoot 'scenarios\sc-02-imagepullbackoff\deployment.yaml' }
    'SC-04' { Join-Path $RepoRoot 'scenarios\sc-04-oomkilled\deployment.yaml' }
}

Write-Output "[1/3] Applying ${Scenario} deployment..."
kubectl apply -f $Deployment
if ($LASTEXITCODE -ne 0) { throw "kubectl apply failed for $Deployment" }

Write-Output '[2/3] Waiting for the deployment to be observed (this waits for EITHER readiness or the incident state; failures are expected here, they are the incident)...'
# --timeout is intentionally modest: for SC-01/SC-02/SC-04 the workload never
# becomes "complete". Do not raise the timeout to mask a non-reproducing scenario
# (spec risk R-02); instead inspect the evidence below.
kubectl rollout status deployment/$(kubectl get deployment -n opspilot-lab -l opspilot.io/scenario=$Scenario -o jsonpath='{.items[0].metadata.name}') -n opspilot-lab --timeout=180s
Write-Output '  (rollout status above failing is EXPECTED for incident scenarios — the incident IS the failure state.)'

Write-Output '[3/3] Current evidence summary for the scenario pod(s):'
kubectl get pods -n opspilot-lab -l opspilot.io/scenario=$Scenario -o wide

$pod = kubectl get pods -n opspilot-lab -l opspilot.io/scenario=$Scenario -o jsonpath='{.items[0].metadata.name}'
if (-not $pod) { throw "No pod found for scenario $Scenario — check kubectl apply output and demo image availability." }

Write-Output ''
Write-Output "--- Pod phase / container states (note: phase and container state are DIFFERENT levels, spec §9.3) ---"
kubectl get pod $pod -n opspilot-lab -o 'jsonpath={.status.phase}{"\n"}'
kubectl get pod $pod -n opspilot-lab -o 'jsonpath={range .status.containerStatuses[*]}container={.name} state={.state} lastState={.lastState} restarts={.restartCount}{"\n"}{end}'

Write-Output ''
Write-Output "--- Recent events (bound to this Pod) ---"
kubectl get events -n opspilot-lab --field-selector involvedObject.name=$pod --sort-by=.lastTimestamp | Select-Object -First 15

Write-Output ''
Write-Output "--- Container logs (current) ---"
kubectl logs $pod -n opspilot-lab --tail=20 2>$null
Write-Output ''
Write-Output "--- Container logs (PREVIOUS instance, when Kubernetes retains them — FR-04) ---"
kubectl logs $pod -n opspilot-lab --previous --tail=20 2>$null
if ($LASTEXITCODE -ne 0) { Write-Output '  (previous logs unavailable — this is recorded as unavailable, never fabricated, NFR-01)' }

Write-Output ''
Write-Output "Incident ${Scenario} is reproductible once you observe the expected state. Freeze the proof into a snapshot:"
Write-Output "  ./scripts/collect-manual-evidence.ps1 -Scenario $Scenario"
Write-Output "Reset afterwards with: ./scripts/reset-scenario.ps1 -Scenario $Scenario"
