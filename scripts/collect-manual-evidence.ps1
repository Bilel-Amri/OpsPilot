# OpsPilot S1 — collect the first REAL evidence snapshot manually (no MCP yet, no AI).
# Usage: ./scripts/collect-manual-evidence.ps1 -Scenario SC-01 [-PodName <name>]
#
# Purpose (S1 exit criterion / gate G1): produce a first validated snapshot with
# identity, timestamps, source and integrity hash for every observation — the
# manual precursor of the S3 EvidenceItem schema (spec §10.3) and of the S2 MCP
# tool outputs (spec §9.2). Missing data is recorded as an explicit
# {"status": "unavailable", "reason": ...} record — NEVER fabricated (NFR-01).
#
# Artifacts land in out/evidence/<SC>/ (git-ignored):
#   pod_status.json, logs_current.json, logs_previous.json, events.json,
#   snapshot_manifest.json (sha256 per file + cluster + collection context).

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('SC-01', 'SC-02', 'SC-04')]
    [string]$Scenario,

    [Parameter(Mandatory = $false)]
    [string]$PodName
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$OutDir   = Join-Path (Join-Path $RepoRoot 'out\evidence') $Scenario
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$collectedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

if (-not $PodName) {
    $PodName = kubectl get pods -n opspilot-lab -l "opspilot.io/scenario=$Scenario" -o jsonpath='{.items[0].metadata.name}'
    if (-not $PodName) { throw "No pod found for scenario $Scenario. Run the scenario first (scripts/run-scenario.ps1)." }
}

Write-Output "Collecting evidence for pod '$PodName' (scenario $Scenario) at $collectedAt ..."

# --- 1. Full Pod status: the identity + phase + container states + spec resources ---
$podJson = kubectl get pod $PodName -n opspilot-lab -o json | ConvertFrom-Json
$podJson | ConvertTo-Json -Depth 32 | Set-Content -Encoding UTF8 (Join-Path $OutDir 'pod_status.json')

$podUid = $podJson.metadata.uid
$resourceVersion = $podJson.metadata.resourceVersion

# --- 2. Logs, current and previous, with full context (FR-04) ---
foreach ($mode in @('current', 'previous')) {
    $file = Join-Path $OutDir ("logs_{0}.json" -f $mode)
    $logText = kubectl logs $PodName -n opspilot-lab $(if ($mode -eq 'previous') { '--previous' }) --tail=200 2>$null
    if ($LASTEXITCODE -eq 0 -and $logText) {
        @{
            status          = "collected"
            collected_at    = $collectedAt
            mode            = $mode
            pod_name        = $PodName
            pod_uid         = $podUid
            namespace       = "opspilot-lab"
            tail_lines      = 200
            text            = @($logText)
        } | ConvertTo-Json | Set-Content -Encoding UTF8 $file
    } else {
        # Absence is recorded with its reason, never neutralized (NFR-01).
        @{
            status          = "unavailable"
            collected_at    = $collectedAt
            mode            = $mode
            pod_name        = $PodName
            pod_uid         = $podUid
            namespace       = "opspilot-lab"
            reason          = "kubectl logs returned nothing/failed for mode=$mode (e.g. container never started, or previous instance not retained)"
        } | ConvertTo-Json | Set-Content -Encoding UTF8 $file
    }
}

# --- 3. Events bound to THIS pod identity (involvedObject.uid), not just same-name (spec §10.4) ---
$eventsJson = kubectl get events -n opspilot-lab -o json --field-selector "involvedObject.name=$PodName" | ConvertFrom-Json
# Second filter on UID: same-name pods across restarts are different identities (spec §10.4).
$uidEvents = @($eventsJson.items | Where-Object { $_.involvedObject.uid -eq $podUid })
@{
    status        = "collected"
    collected_at  = $collectedAt
    pod_name      = $PodName
    pod_uid       = $podUid
    namespace     = "opspilot-lab"
    items         = $uidEvents
} | ConvertTo-Json -Depth 16 | Set-Content -Encoding UTF8 (Join-Path $OutDir 'events.json')

# --- 4. Snapshot manifest: context + integrity hashes (precursor of snapshot_id/payload_hash, spec §10.3) ---
$clusterVersion = (kubectl version -o json 2>$null | ConvertFrom-Json).serverVersion.gitVersion
$files = @('pod_status.json', 'logs_current.json', 'logs_previous.json', 'events.json')
$hashes = @{}
foreach ($f in $files) {
    $p = Join-Path $OutDir $f
    if (Test-Path $p) { $hashes[$f] = (Get-FileHash -Algorithm SHA256 $p).Hash.ToLowerInvariant() }
}
@{
    scenario_id        = $Scenario
    collected_at       = $collectedAt
    cluster_version    = $clusterVersion
    namespace          = "opspilot-lab"
    pod_name           = $PodName
    pod_uid            = $podUid
    pod_resource_version = $resourceVersion
    collected_by       = "manual kubectl (S1-09) — MCP collection arrives in S2"
    payload_sha256     = $hashes
    notes              = "resourceVersion is an API object version, NOT a timestamp (spec §10.4) — never used as a clock."
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $OutDir 'snapshot_manifest.json')

Write-Output ''
Write-Output 'Snapshot written:'
Get-ChildItem $OutDir | ForEach-Object { Write-Output ("  {0}  ({1} bytes)" -f $_.Name, $_.Length) }
Write-Output ''
Write-Output 'Validate: all files parse as JSON, the manifest hashes match, unavailable records have explicit reasons.'
Write-Output 'This snapshot is the G1 evidence base that Bilel reviews before S3 EQG rule drafting.'
