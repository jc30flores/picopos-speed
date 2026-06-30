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
        "$svc $($service.Status) StartName=$(Get-ServiceStartNameSafe -Name $svc)"
    } else {
        "$svc not-installed"
    }
}
Save-Diagnostic "services.txt" ($serviceLines -join "`n")
Save-Diagnostic "status.txt" ((& "$PSScriptRoot\status.ps1" 2>&1 | ForEach-Object { [string]$_ }) -join "`n")

function Get-PicoServiceAccountDiagnostic {
    $accountName = $Script:PicoServiceAccountName
    if (Get-Command Get-LocalUser -ErrorAction SilentlyContinue) {
        try {
            $user = Get-LocalUser -Name $accountName -ErrorAction Stop
            $expires = if ($null -eq $user.PasswordExpires) { "never" } else { [string]$user.PasswordExpires }
            $never = if ($null -eq $user.PasswordExpires) { "true" } else { "false" }
            return "exists Enabled=$($user.Enabled) SID=$($user.SID.Value) PasswordExpires=$expires PasswordNeverExpires=$never"
        } catch {
        }
    }
    try {
        $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $accountName)
        $null = $user.Name
        $flags = [int]$user.UserFlags.Value
        $never = (($flags -band 0x10000) -ne 0)
        return "exists provider=ADSI PasswordNeverExpires=$never"
    } catch {
        return "missing"
    }
}
Save-Diagnostic "service-account.txt" (Get-PicoServiceAccountDiagnostic)

$dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
$postgresDataFacts = foreach ($fileName in @("PG_VERSION", "postgresql.conf", "pg_hba.conf")) {
    "$fileName=$(if (Test-Path -LiteralPath (Join-Path $dataDir $fileName) -PathType Leaf) { 'present' } else { 'missing' })"
}
Save-Diagnostic "postgres-data.txt" ($postgresDataFacts -join "`n")

$postgresXml = Join-Path (Join-Path $Script:ProgramFilesDir "services") "PicoDeGallo-PostgreSQL.xml"
if (Test-Path -LiteralPath $postgresXml -PathType Leaf) {
    $postgresXmlContent = Get-Content -LiteralPath $postgresXml -Raw -ErrorAction SilentlyContinue
    $postgresXmlFacts = @(
        "serviceaccount=$(if ($postgresXmlContent -match '<serviceaccount>') { 'present' } else { 'absent' })",
        "password_field=$(if ($postgresXmlContent -match '<password>') { 'present' } else { 'absent' })",
        "pico_user=$(if ($postgresXmlContent -match [regex]::Escape($Script:PicoServiceAccountName)) { 'present' } else { 'absent' })"
    )
    Save-Diagnostic "postgres-serviceaccount.txt" ($postgresXmlFacts -join "`n")
}

$serviceDir = Join-Path $Script:ProgramFilesDir "services"
$serviceFileFacts = @()
foreach ($svc in $Script:Services) {
    $xml = Join-Path $serviceDir "$svc.xml"
    $exe = Join-Path $serviceDir "$svc.exe"
    $serviceFileFacts += "$svc.xml=$(if (Test-Path -LiteralPath $xml -PathType Leaf) { 'present' } else { 'missing' })"
    $serviceFileFacts += "$svc.exe=$(if (Test-Path -LiteralPath $exe -PathType Leaf) { 'present' } else { 'missing' })"
    if (Test-Path -LiteralPath $xml -PathType Leaf) {
        Save-Diagnostic "service-xml-$svc.txt" (Get-Content -LiteralPath $xml -Raw -ErrorAction SilentlyContinue)
    }
}
Save-Diagnostic "service-files.txt" ($serviceFileFacts -join "`n")

$caddyfile = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile"
Save-Diagnostic "caddyfile.txt" ("Caddyfile=$(if (Test-Path -LiteralPath $caddyfile -PathType Leaf) { 'present' } else { 'missing' })")

function Get-BackendRuntimeDiagnostic {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    $facts = @(
        "python=$(if (Test-Path -LiteralPath $python -PathType Leaf) { 'present' } else { 'missing' })",
        "manage.py=$(if (Test-Path -LiteralPath (Join-Path $backend 'manage.py') -PathType Leaf) { 'present' } else { 'missing' })",
        "config.settings=$(if (Test-Path -LiteralPath (Join-Path $backend 'config\settings.py') -PathType Leaf) { 'present' } else { 'missing' })",
        "config.wsgi=$(if (Test-Path -LiteralPath (Join-Path $backend 'config\wsgi.py') -PathType Leaf) { 'present' } else { 'missing' })",
        "check_runtime_config=$(if (Test-Path -LiteralPath (Join-Path $backend 'apps\core\management\commands\check_runtime_config.py') -PathType Leaf) { 'present' } else { 'missing' })"
    )
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $backend "manage.py") -PathType Leaf)) {
        return ($facts -join "`n")
    }

    $envNames = @("DJANGO_ENV_FILE", "DOTENV_OVERRIDE", "DJANGO_SETTINGS_MODULE", "PYTHONUNBUFFERED")
    $oldEnv = @{}
    foreach ($name in $envNames) {
        $oldEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    }
    try {
        [Environment]::SetEnvironmentVariable("DJANGO_ENV_FILE", (Get-EnvPath), "Process")
        [Environment]::SetEnvironmentVariable("DOTENV_OVERRIDE", "false", "Process")
        [Environment]::SetEnvironmentVariable("DJANGO_SETTINGS_MODULE", "config.settings", "Process")
        [Environment]::SetEnvironmentVariable("PYTHONUNBUFFERED", "1", "Process")
        Push-Location $backend
        try {
            $output = & $python -c "import importlib, os; module=os.environ.get('DJANGO_SETTINGS_MODULE') or 'config.settings'; print('DJANGO_SETTINGS_MODULE=' + module); importlib.import_module(module); importlib.import_module('config.wsgi'); print('DJANGO_SETTINGS_IMPORT_OK')" 2>&1
            $facts += "settings_import_exit=$LASTEXITCODE"
            $facts += ($output | ForEach-Object { [string]$_ })
            $helpOutput = & $python manage.py help check_runtime_config 2>&1
            $facts += "check_runtime_config_help_exit=$LASTEXITCODE"
            $facts += ($helpOutput | Select-Object -First 40 | ForEach-Object { [string]$_ })
        } finally {
            Pop-Location
        }
    } catch {
        $facts += "backend_runtime_exception=$($_.Exception.Message)"
    } finally {
        foreach ($name in $envNames) {
            [Environment]::SetEnvironmentVariable($name, $oldEnv[$name], "Process")
        }
    }
    return ($facts -join "`n")
}
Save-Diagnostic "backend-runtime.txt" (Get-BackendRuntimeDiagnostic)

$runAsDir = Join-Path (Get-LogsDir) "runas"
if (Test-Path -LiteralPath $runAsDir -PathType Container) {
    $runAsFiles = Get-ChildItem -LiteralPath $runAsDir -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 40
    $runAsLines = foreach ($file in $runAsFiles) {
        "$($file.Name) LastWriteTime=$($file.LastWriteTime.ToString('o')) Size=$($file.Length)"
    }
    Save-Diagnostic "runas-files.txt" ($runAsLines -join "`n")
    $latestExit = $runAsFiles | Where-Object { $_.Name -like "*.exitcode" } | Select-Object -First 1
    if ($latestExit) {
        Save-Diagnostic "runas-last-exitcode.txt" (Get-Content -LiteralPath $latestExit.FullName -Raw -ErrorAction SilentlyContinue)
    }
    foreach ($file in ($runAsFiles | Where-Object { $_.Extension -in @(".log", ".exitcode", ".done") } | Select-Object -First 12)) {
        Save-Diagnostic "runas-$($file.Name).txt" ((Get-Content -LiteralPath $file.FullName -Tail 120 -ErrorAction SilentlyContinue) -join "`n")
    }
}

$installServicesError = Join-Path (Get-LogsDir) "install-services-error.log"
if (Test-Path -LiteralPath $installServicesError -PathType Leaf) {
    Save-Diagnostic "install-services-error-tail.txt" ((Get-Content -LiteralPath $installServicesError -Tail 200 -ErrorAction SilentlyContinue) -join "`n")
}

$icacls = Join-Path $env:SystemRoot "System32\icacls.exe"
if (Test-Path -LiteralPath $icacls -PathType Leaf) {
    $aclTargets = @(
        (Join-Path $Script:ProgramDataDir "postgres"),
        (Join-Path $Script:ProgramDataDir "postgres\data"),
        (Join-Path $Script:ProgramDataDir "logs"),
        (Join-Path $Script:ProgramFilesDir "postgres"),
        (Join-Path $Script:ProgramFilesDir "services")
    )
    $aclLines = foreach ($target in $aclTargets) {
        if (Test-Path -LiteralPath $target) {
            "ACL_BEGIN $target"
            & $icacls $target 2>&1 | ForEach-Object { [string]$_ }
            "ACL_END $target"
        } else {
            "ACL_MISSING $target"
        }
    }
    Save-Diagnostic "acls.txt" ($aclLines -join "`n")
}

$envs = Read-NativeEnv
$dteTokenName = "DTE_" + "API_TOKEN"
$safe = [ordered]@{
    APP_HTTP_PORT = $envs["APP_HTTP_PORT"]
    APP_BIND_ADDRESS = $envs["APP_BIND_ADDRESS"]
    DTE_BACKGROUND_MODE = $envs["DTE_BACKGROUND_MODE"]
    DTE_MONITOR_ENABLED = $envs["DTE_MONITOR_ENABLED"]
    DTE_OUTBOX_WORKER_ENABLED = $envs["DTE_OUTBOX_WORKER_ENABLED"]
    DTE_BASE_URL = $(if ($envs["DTE_BASE_URL"] -like "replace-with-*") { "placeholder" } else { "configured" })
    DTE_TOKEN_STATUS = $(if ($envs[$dteTokenName] -like "replace-with-*") { "placeholder" } else { "configured" })
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
