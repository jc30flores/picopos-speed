$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

$stamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
$root = Join-Path (Get-DiagnosticsDir) "diag-$stamp"
New-DirectorySafe $root

function Save-Diagnostic {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Text
    )
    Set-Content -LiteralPath (Join-Path $root $Name) -Value (Protect-Text $Text) -Encoding UTF8
}

Save-Diagnostic "windows.txt" ([Environment]::OSVersion.VersionString)
Save-Diagnostic "powershell.txt" ($PSVersionTable | Out-String)

$serviceLines = foreach ($svc in $Script:Services) {
    $service = Get-ServiceSafe $svc
    if ($service) {
        "$svc $($service.Status)"
    } else {
        "$svc not-installed"
    }
}
Save-Diagnostic "services.txt" ($serviceLines -join "`n")
Save-Diagnostic "status.txt" ((& "$PSScriptRoot\status.ps1" 2>&1 | ForEach-Object { [string]$_ }) -join "`n")

$envs = Read-NativeEnv
$safe = [ordered]@{
    APP_HTTP_PORT = $envs["APP_HTTP_PORT"]
    APP_BIND_ADDRESS = $envs["APP_BIND_ADDRESS"]
    DTE_BACKGROUND_MODE = $envs["DTE_BACKGROUND_MODE"]
    DTE_MONITOR_ENABLED = $envs["DTE_MONITOR_ENABLED"]
    DTE_OUTBOX_WORKER_ENABLED = $envs["DTE_OUTBOX_WORKER_ENABLED"]
    DTE_BASE_URL = $(if ($envs["DTE_BASE_URL"] -like "replace-with-*") { "placeholder" } else { "configured" })
    DTE_API_TOKEN = $(if ($envs["DTE_API_TOKEN"] -like "replace-with-*") { "placeholder" } else { "configured" })
    PICO_BOOTSTRAP_ADMIN_ENABLED = $envs["PICO_BOOTSTRAP_ADMIN_ENABLED"]
    PICO_BOOTSTRAP_ADMIN_USERNAME = $(if ([string]::IsNullOrWhiteSpace([string]$envs["PICO_BOOTSTRAP_ADMIN_USERNAME"])) { "not-configured" } else { "configured" })
}
Save-Diagnostic "config-safe.json" ($safe | ConvertTo-Json -Depth 3)

$appUrl = Get-AppUrl
function Get-HealthStatus {
    param([Parameter(Mandatory = $true)][string]$Uri)
    try {
        return [string](Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5).StatusCode
    } catch {
        return "error"
    }
}
$rootHealth = Get-HealthStatus -Uri $appUrl
$liveHealth = Get-HealthStatus -Uri ($appUrl + "/api/health/live/")
$readyHealth = Get-HealthStatus -Uri ($appUrl + "/api/health/ready/")
Save-Diagnostic "health.txt" ((@(
    "root=$rootHealth",
    "live=$liveHealth",
    "ready=$readyHealth"
) -join "`n"))

foreach ($log in Get-ChildItem (Get-LogsDir) -Filter "*.log" -ErrorAction SilentlyContinue) {
    Save-Diagnostic "log-$($log.Name).txt" ((Get-Content -LiteralPath $log.FullName -Tail 300) -join "`n")
}

$zip = Join-Path (Get-DiagnosticsDir) "PicoDeGallo-Native-Diagnostico-$stamp.zip"
Compress-Archive -Path (Join-Path $root "*") -DestinationPath $zip -Force
Remove-Item -LiteralPath $root -Recurse -Force
Write-SafeHost "Diagnostico generado: $zip"
