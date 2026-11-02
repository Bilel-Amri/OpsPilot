# OpsPilot S1 — build the demo-app image and load it into the Kind cluster.
# Prerequisites: create-cluster.ps1 succeeded (G0 passed, cluster "opspilot" exists).

$ErrorActionPreference = 'Stop'

$ImageTag = 'opspilot/demo-app:s1'
$Cluster  = 'opspilot'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DemoDir  = Join-Path $RepoRoot 'demo-app'

Write-Output "[1/2] Building demo image ${ImageTag} (docker build)..."
docker build -t $ImageTag $DemoDir
if ($LASTEXITCODE -ne 0) { throw 'docker build failed. Is the Docker Engine running? (check-environment.ps1)' }

Write-Output "[2/2] Loading ${ImageTag} into kind cluster ${Cluster}..."
kind load docker-image $ImageTag --name $Cluster
if ($LASTEXITCODE -ne 0) { throw 'kind load docker-image failed.' }

Write-Output ''
Write-Output "Image available inside the cluster: ${ImageTag}"
Write-Output 'SC-02 is intentionally NOT built (its manifest pulls from an unresolvable .invalid host on purpose — see its header).'
Write-Output 'Next: scripts/run-scenario.ps1 -Scenario SC-01'
