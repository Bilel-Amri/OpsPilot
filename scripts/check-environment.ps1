# OpsPilot S0 — environment verification (docs/project/S0_S1_PLAN.md S0.1).
# Prints a GO/NO-GO per prerequisite item; exits non-zero if any mandatory item is NO-GO.
# This script never installs anything: installs are explicit operator actions.

$ErrorActionPreference = 'Continue'
$failures = @()

function Test-Item {
    param(
        [string]$Name,
        [scriptblock]$Check,
        [switch]$Mandatory
    )
    try {
        $result = & $Check
        if ($result) {
            Write-Output ("[GO ] {0} {1}" -f $Name, $result)
        } else {
            Write-Output ("[NO-GO] {0}" -f $Name)
            if ($Mandatory) { $script:failures += $Name }
        }
    } catch {
        Write-Output ("[NO-GO] {0} ({1})" -f $Name, $_.Exception.Message.Trim())
        if ($Mandatory) { $script:failures += $Name }
    }
}

$dockerClient = Get-Command docker -ErrorAction SilentlyContinue
Test-Item 'Docker CLI present' { if ($dockerClient) { (docker version --format '{{.Client.Version}}') } }

Test-Item 'Docker Engine daemon reachable' {
    # The engine must actually answer (spec 4.4: verify Docker Desktop / WSL2 before Kind)
    docker info --format 'Engine v{{.ServerVersion}} ({{.OperatingSystem}})' 2>$null
} -Mandatory

Test-Item 'WSL2 available (docker-desktop needs it)' {
    $wsl = wsl.exe --status 2>$null | Out-String
    if ($LASTEXITCODE -eq 0 -and $wsl -match '2') { 'WSL2 default version = 2' }
} 

Test-Item 'Kind installed' {
    # Expected NO-GO at repository initialization; operator installs manually (no auto-install).
    kind version
} -Mandatory

Test-Item 'kubectl client' {
    (kubectl version --client=true 2>$null | Select-Object -First 1)
} -Mandatory

# Kubernetes client skew: kubectl must be within one minor of the pinned node
# server (1.37.0) -> supported clients are 1.36-1.38. A too-old client does not
# hard-fail (kind tasks still work locally) but is reported as a warning so the
# operator upgrades it manually before G0 (no auto-install).
$clientMinor = $null
try {
    $clientLine = (kubectl version --client=true 2>$null | Select-Object -First 1) -as [string]
    if ($clientLine -match 'v1\.(\d+)\.') { $clientMinor = [int]$Matches[1] }
} catch { }
if ($clientMinor -and $clientMinor -lt 36) {
    Write-Output ("[WARN] kubectl client minor 1.{0} is below the skew window (1.36-1.38) for the pinned node image 1.37.0 - upgrade the client manually before G0." -f $clientMinor)
}

Test-Item 'Git' { git --version } -Mandatory

Test-Item 'Python >= 3.11 (MCP SDK v2 requirement, spec 4.4)' {
    $v = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    $minorOk = [int]($v.Split('.')[1]) -ge 11 -and [int]($v.Split('.')[0]) -ge 3
    if ($minorOk) { "python $v" } else { $null }
} -Mandatory

$cs = Get-CimInstance Win32_ComputerSystem
$freeRamGB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB, 1)
$totalRamGB = [math]::Round($cs.TotalPhysicalMemory/1GB, 1)
$freeDiskGB = [math]::Round((Get-PSDrive C).Free/1GB, 1)
Test-Item 'Hardware: >= 8 GB RAM total' { if ($totalRamGB -ge 8) { "total ram ${totalRamGB} GB (free right now: ${freeRamGB} GB)" } }
Test-Item 'Hardware: >= 20 GB free disk on C:' { if ($freeDiskGB -ge 20) { "free disk ${freeDiskGB} GB" } }
if ($freeRamGB -lt 4) {
    Write-Output "[WARN] Free RAM is only ${freeRamGB} GB - close memory-heavy apps before creating the cluster (spec 20.5 sequential-mode fallback)."
}

Write-Output ''
if ($failures.Count -gt 0) {
    Write-Output ("RESULT: NO-GO overall. Missing: {0}" -f ($failures -join ', '))
    Write-Output 'Action: fix the items above manually, then re-run this script (nothing is auto-installed, per docs/project/S0_S1_PLAN.md S0.1).'
    exit 1
}
Write-Output 'RESULT: GO - all mandatory items answered. Proceed with scripts/create-cluster.ps1.'
