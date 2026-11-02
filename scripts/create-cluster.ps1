# OpsPilot S1 — create the Kind cluster, apply the lab namespace and read-only RBAC.
# Prerequisites: scripts/check-environment.ps1 → GO (gate G0).
# The script fails loudly at the first failed step (NFR-01: errors are surfaced, never masked).

$ErrorActionPreference = 'Stop'

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$KindConfig = Join-Path $RepoRoot 'k8s\kind-config.yaml'
$RbacDir    = Join-Path $RepoRoot 'k8s\rbac'

Write-Output '[1/4] Creating Kind cluster (this takes a few minutes on first run)...'
kind create cluster --config $KindConfig
if ($LASTEXITCODE -ne 0) { throw 'kind create cluster failed.' }

Write-Output '[2/4] Pointing kubectl at the new cluster context...'
kubectl config use-context kind-opspilot
kubectl cluster-info

Write-Output '[3/4] Applying lab namespace and read-only RBAC...'
foreach ($file in @('namespace.yaml','serviceaccount.yaml','role.yaml','rolebinding.yaml')) {
    $path = Join-Path $RbacDir $file
    Write-Output "  apply $file"
    kubectl apply -f $path
    if ($LASTEXITCODE -ne 0) { throw "kubectl apply failed for $file" }
}

Write-Output '[4/4] Verifying the RBAC refusals that OpsPilot depends on (SEC-02)...'
$sa = 'system:serviceaccount:opspilot-lab:opspilot-mcp'
$expectations = @(
    @{ Resource = 'get pods';        Allowed = $true  },
    @{ Resource = 'list pods';       Allowed = $true  },
    @{ Resource = 'get pods/log';    Allowed = $true  },
    @{ Resource = 'list events';     Allowed = $true  },
    @{ Resource = 'create pods';     Allowed = $false },
    @{ Resource = 'delete pods';     Allowed = $false },
    @{ Resource = 'get secrets';     Allowed = $false },
    @{ Resource = 'patch deployments'; Allowed = $false }
)
$wrong = 0
foreach ($exp in $expectations) {
    $parts = $exp.Resource.Split(' ')
    $answer = kubectl auth can-i --as=$sa $parts[0] $parts[1] -n opspilot-lab 2>$null
    $ok = if ($exp.Allowed) { $answer -eq 'yes' } else { $answer -eq 'no' }
    $tag = if ($ok) { 'OK ' } else { 'VIOLATION' }
    if (-not $ok) { $wrong++ }
    Write-Output ("  [{0}] {1,-18} -> {2}" -f $tag, $exp.Resource, $answer)
}
if ($wrong -gt 0) { throw "RBAC verification failed ($wrong violation(s)). Do not continue to S2 before fixing k8s/rbac." }

Write-Output ''
Write-Output 'Cluster ready (namespace opspilot-lab, read-only SA opspilot-mcp verified).'
Write-Output 'Next: scripts/build-load-demo-image.ps1, then scripts/run-scenario.ps1 -Scenario SC-01.'
