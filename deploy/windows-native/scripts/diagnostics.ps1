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
    [System.IO.File]::WriteAllText((Join-Path $root $Name), (Protect-Text $Text), (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false)))
}

Save-Diagnostic "windows.txt" ([Environment]::OSVersion.VersionString)
Save-Diagnostic "powershell.txt" ($PSVersionTable | Out-String)
$installProfile = Get-WindowsInstallProfile
$installProfileLines = foreach ($key in @($installProfile.Keys)) {
    "INSTALL_PROFILE {0}={1}" -f $key, [string]$installProfile[$key]
}
Save-Diagnostic "install-profile.txt" ($installProfileLines -join "`n")
if (Test-Path -LiteralPath (Get-InstallStatePath) -PathType Leaf) {
    Save-Diagnostic "install-state.json" (Get-Content -LiteralPath (Get-InstallStatePath) -Raw -ErrorAction SilentlyContinue)
}
if (Test-Path -LiteralPath (Get-RuntimePortsPath) -PathType Leaf) {
    Save-Diagnostic "runtime-ports.json" (Get-Content -LiteralPath (Get-RuntimePortsPath) -Raw -ErrorAction SilentlyContinue)
}

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
if (Test-Path -LiteralPath $caddyfile -PathType Leaf) {
    $caddyContent = Get-Content -LiteralPath $caddyfile -Raw -ErrorAction SilentlyContinue
    $numbered = @()
    $lineNo = 0
    foreach ($line in @(Get-Content -LiteralPath $caddyfile -ErrorAction SilentlyContinue)) {
        $lineNo += 1
        $numbered += ("{0,4}: {1}" -f $lineNo, [string]$line)
    }
    Save-Diagnostic "caddyfile-numbered.txt" ($numbered -join "`n")
    $caddyFacts = @(
        "auto_https_off=$(if ($caddyContent -match '(?m)^\s*auto_https\s+off\s*$') { 'true' } else { 'false' })",
        "http_loopback_site=$(if ($caddyContent -match '(?m)^\s*http://127\.0\.0\.1:\d+\s*\{') { 'true' } else { 'false' })",
        "bind_loopback=$(if ($caddyContent -match '(?m)^\s*bind\s+127\.0\.0\.1\s*$') { 'true' } else { 'false' })",
        "bare_loopback_site=$(if ($caddyContent -match '(?m)^\s*127\.0\.0\.1:\d+\s*\{') { 'true' } else { 'false' })",
        "quoted_program_files_root=$(if ($caddyContent -match 'root\s+\*\s+"C:/Program Files/') { 'true' } else { 'false' })",
        "quoted_programdata_root=$(if ($caddyContent -match 'root\s+\*\s+"C:/ProgramData/') { 'true' } else { 'false' })"
    )
    Save-Diagnostic "caddyfile-http-local.txt" ($caddyFacts -join "`n")
}

$frontendDir = Join-Path $Script:ProgramFilesDir "frontend"
$frontendIndex = Join-Path $frontendDir "index.html"
Save-Diagnostic "frontend-payload.txt" ((@(
    "frontend_dir=$(if (Test-Path -LiteralPath $frontendDir -PathType Container) { 'present' } else { 'missing' })",
    "frontend-index=$(if (Test-Path -LiteralPath $frontendIndex -PathType Leaf) { 'present' } else { 'missing' })"
) -join "`n"))

function ConvertTo-DiagnosticArgumentString {
    param([string[]]$ArgumentList = @())

    return (Join-WindowsCommandLineArguments -ArgumentList $ArgumentList)
}

function Invoke-DiagnosticProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )

    $safeCommandParts = @($FilePath) + @($ArgumentList)
    $safeCommand = ($safeCommandParts | ForEach-Object {
        $part = [string]$_
        if ($part -match '\s') { '"' + $part.Replace('"', '\"') + '"' } else { $part }
    }) -join " "
    $lines = @("RUN $safeCommand")
    $stdoutText = ""
    $stderrText = ""
    $exitCode = 1
    $process = New-Object System.Diagnostics.Process
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $FilePath
        $psi.Arguments = ConvertTo-DiagnosticArgumentString -ArgumentList $ArgumentList
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            $psi.WorkingDirectory = $WorkingDirectory
        }
        foreach ($name in @($Environment.Keys | Sort-Object)) {
            $psi.EnvironmentVariables[[string]$name] = [string]$Environment[$name]
        }
        $process.StartInfo = $psi
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdoutTask.Wait()
        $stderrTask.Wait()
        $exitCode = [int]$process.ExitCode
        $stdoutText = [string]$stdoutTask.Result
        $stderrText = [string]$stderrTask.Result
    } catch {
        $lines += "COMMAND_LAUNCH_FAILED exceptionType=$($_.Exception.GetType().FullName)"
        $lines += "exception=$($_.Exception.ToString())"
    } finally {
        if ($process) {
            $process.Dispose()
        }
    }

    $lines += "EXIT_CODE $exitCode"
    if (-not [string]::IsNullOrWhiteSpace($stdoutText)) {
        $lines += "STDOUT_BEGIN"
        $lines += ($stdoutText -split "`r?`n" | ForEach-Object { [string]$_ })
        $lines += "STDOUT_END"
    }
    if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
        $lines += "STDERR_BEGIN"
        $lines += ($stderrText -split "`r?`n" | ForEach-Object { [string]$_ })
        $lines += "STDERR_END"
        if ($exitCode -eq 0) {
            $lines += "STDERR_NONFATAL exitCode=0"
        }
    }
    return $lines
}

function Invoke-DiagnosticProcessCapture {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )

    $stdoutText = ""
    $stderrText = ""
    $exitCode = 1
    $process = New-Object System.Diagnostics.Process
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $FilePath
        $psi.Arguments = ConvertTo-DiagnosticArgumentString -ArgumentList $ArgumentList
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            $psi.WorkingDirectory = $WorkingDirectory
        }
        foreach ($name in @($Environment.Keys | Sort-Object)) {
            $psi.EnvironmentVariables[[string]$name] = [string]$Environment[$name]
        }
        $process.StartInfo = $psi
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdoutTask.Wait()
        $stderrTask.Wait()
        $exitCode = [int]$process.ExitCode
        $stdoutText = [string]$stdoutTask.Result
        $stderrText = [string]$stderrTask.Result
    } catch {
        $stderrText = "COMMAND_LAUNCH_FAILED exceptionType=$($_.Exception.GetType().FullName)`n$($_.Exception.ToString())"
    } finally {
        if ($process) {
            $process.Dispose()
        }
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Stdout = $stdoutText
        Stderr = $stderrText
    }
}

$caddyExe = Join-Path $Script:ProgramFilesDir "caddy\caddy.exe"
if ((Test-Path -LiteralPath $caddyExe -PathType Leaf) -and (Test-Path -LiteralPath $caddyfile -PathType Leaf)) {
    $caddyValidate = Invoke-DiagnosticProcessCapture `
        -FilePath $caddyExe `
        -ArgumentList @("validate", "--config", $caddyfile) `
        -WorkingDirectory (Join-Path $Script:ProgramFilesDir "caddy")
    Save-Diagnostic "caddy-validate-exit.txt" ("EXIT_CODE {0}" -f $caddyValidate.ExitCode)
    Save-Diagnostic "caddy-validate-stdout.txt" ([string]$caddyValidate.Stdout)
    Save-Diagnostic "caddy-validate-stderr.txt" ([string]$caddyValidate.Stderr)
}

$netstatExe = Join-Path $env:SystemRoot "System32\netstat.exe"
if (Test-Path -LiteralPath $netstatExe -PathType Leaf) {
    $netstatAll = & $netstatExe -ano 2>&1 | ForEach-Object { [string]$_ }
    foreach ($port in @("5432", "8000", "9282")) {
        $netstatLines = $netstatAll | Where-Object { [string]$_ -match ":$port\s" } | ForEach-Object { [string]$_ }
        Save-Diagnostic "netstat-$port.txt" ($netstatLines -join "`n")
    }
    $caddyNetstat = $netstatAll | Where-Object { [string]$_ -match ":9282\s" } | ForEach-Object { [string]$_ }
    Save-Diagnostic "netstat-9282-bind.txt" ((@(
        "listens_0_0_0_0=$(if (($caddyNetstat -join "`n") -match '0\.0\.0\.0:9282') { 'true' } else { 'false' })",
        "listens_127_0_0_1=$(if (($caddyNetstat -join "`n") -match '127\.0\.0\.1:9282') { 'true' } else { 'false' })"
    ) -join "`n"))
}

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

    $runtimeEnv = @{
        DJANGO_ENV_FILE = (Get-EnvPath)
        DOTENV_OVERRIDE = "false"
        DJANGO_SETTINGS_MODULE = "config.settings"
        PYTHONUNBUFFERED = "1"
        PYTHONDONTWRITEBYTECODE = "1"
        PICO_INSTALLER_PREFLIGHT = "1"
    }

    $facts += Invoke-DiagnosticProcess `
        -FilePath $python `
        -ArgumentList @("-c", "import importlib, os; module=os.environ.get('DJANGO_SETTINGS_MODULE') or 'config.settings'; print('DJANGO_SETTINGS_MODULE=' + module); importlib.import_module(module); importlib.import_module('config.wsgi'); print('DJANGO_SETTINGS_IMPORT_OK')") `
        -WorkingDirectory $backend `
        -Environment $runtimeEnv

    $helpResult = Invoke-DiagnosticProcess `
        -FilePath $python `
        -ArgumentList @("manage.py", "help", "check_runtime_config") `
        -WorkingDirectory $backend `
        -Environment $runtimeEnv
    $facts += "check_runtime_config_help_exit=$(($helpResult | Where-Object { $_ -like 'EXIT_CODE *' } | Select-Object -First 1).Replace('EXIT_CODE ', ''))"
    $facts += $helpResult

    $facts += Invoke-DiagnosticProcess `
        -FilePath $python `
        -ArgumentList @("manage.py", "check_runtime_config") `
        -WorkingDirectory $backend `
        -Environment $runtimeEnv

    $envs = Read-NativeEnv
    $dbHost = [string]$envs["DB_HOST"]
    if ([string]::IsNullOrWhiteSpace($dbHost)) { $dbHost = "127.0.0.1" }
    $dbPort = 5432
    if (-not [string]::IsNullOrWhiteSpace([string]$envs["DB_PORT"])) {
        [void][int]::TryParse([string]$envs["DB_PORT"], [ref]$dbPort)
    }
    if (Test-TcpPort -HostName $dbHost -Port $dbPort -TimeoutMilliseconds 1000) {
        $dbScript = @"
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT 1")
    value = cursor.fetchone()[0]
print("DJANGO_DB_SELECT_OK value=" + str(value))
"@
        $facts += Invoke-DiagnosticProcess `
            -FilePath $python `
            -ArgumentList @("-c", $dbScript) `
            -WorkingDirectory $backend `
            -Environment $runtimeEnv
    } else {
        $facts += "DJANGO_DB_SELECT_SKIPPED postgres_tcp_unavailable $dbHost`:$dbPort"
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
    Save-Diagnostic "install-services-error.log" (Get-Content -LiteralPath $installServicesError -Raw -ErrorAction SilentlyContinue)
    Save-Diagnostic "install-services-error-tail.txt" ((Get-Content -LiteralPath $installServicesError -Tail 200 -ErrorAction SilentlyContinue) -join "`n")
}

$backendRuntimeLog = Join-Path (Get-LogsDir) "backend-runtime.log"
if (Test-Path -LiteralPath $backendRuntimeLog -PathType Leaf) {
    Save-Diagnostic "backend-runtime.log" (Get-Content -LiteralPath $backendRuntimeLog -Raw -ErrorAction SilentlyContinue)
}

$failedCommandFiles = Get-ChildItem -LiteralPath (Get-LogsDir) -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "failed-*-stdout.log" -or $_.Name -like "failed-*-stderr.log" } |
    Sort-Object LastWriteTime -Descending
foreach ($file in $failedCommandFiles) {
    Save-Diagnostic "failed-$($file.Name).txt" (Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue)
}

foreach ($snapshotName in @("migration-plan.log", "django-migrations-snapshot.log", "pg-indexes-snapshot.log", "migration-diagnostics.log")) {
    $snapshotPath = Join-Path (Get-LogsDir) $snapshotName
    if (Test-Path -LiteralPath $snapshotPath -PathType Leaf) {
        Save-Diagnostic $snapshotName (Get-Content -LiteralPath $snapshotPath -Raw -ErrorAction SilentlyContinue)
    }
}

$tmpFiles = Get-ChildItem -LiteralPath (Get-LogsDir) -File -Filter "*.tmp" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending
$tmpLines = foreach ($file in $tmpFiles) {
    "$($file.Name) LastWriteTime=$($file.LastWriteTime.ToString('o')) Size=$($file.Length)"
}
Save-Diagnostic "tmp-files.txt" ($tmpLines -join "`n")

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
$dteBaseUrl = [string]$envs["DTE_BASE_URL"]
$dteToken = [string]$envs[$dteTokenName]
$dteBaseUrlLooksReady = $false
$dteBaseUri = $null
if (-not [string]::IsNullOrWhiteSpace($dteBaseUrl) -and [Uri]::TryCreate($dteBaseUrl, [UriKind]::Absolute, [ref]$dteBaseUri)) {
    $host = if ($dteBaseUri.Host) { $dteBaseUri.Host.ToLowerInvariant() } else { "" }
    $dteBaseUrlLooksReady = ($dteBaseUri.Scheme -in @("http", "https")) -and
        -not [string]::IsNullOrWhiteSpace($host) -and
        $host -notin @("example.com", "www.example.com", "localhost", "127.0.0.1") -and
        -not $host.EndsWith(".invalid") -and
        $dteBaseUrl -notmatch "(?i)replace-with|placeholder|changeme|example"
}
$dteTokenLooksReady = -not [string]::IsNullOrWhiteSpace($dteToken) -and $dteToken -notmatch "(?i)replace-with|placeholder|changeme|example"
$dteConfigReady = $dteBaseUrlLooksReady -and $dteTokenLooksReady
$safe = [ordered]@{
    PICO_PORT_MODE = $envs["PICO_PORT_MODE"]
    DB_PORT = $envs["DB_PORT"]
    BACKEND_HTTP_PORT = $envs["BACKEND_HTTP_PORT"]
    APP_HTTP_PORT = $envs["APP_HTTP_PORT"]
    APP_BIND_ADDRESS = $envs["APP_BIND_ADDRESS"]
    DTE_BACKGROUND_MODE = $envs["DTE_BACKGROUND_MODE"]
    DTE_MONITOR_ENABLED = $envs["DTE_MONITOR_ENABLED"]
    DTE_OUTBOX_WORKER_ENABLED = $envs["DTE_OUTBOX_WORKER_ENABLED"]
    DTE_BASE_URL = $(if ($dteBaseUrlLooksReady) { "configured" } else { "placeholder-or-invalid" })
    DTE_TOKEN_STATUS = $(if ($dteTokenLooksReady) { "configured" } else { "placeholder-or-invalid" })
    DTE_CONFIG_READY = [string]$dteConfigReady
    DTE_CONFIG_PENDING = [string](-not $dteConfigReady)
    PICO_BOOTSTRAP_ADMIN_ENABLED = $envs["PICO_BOOTSTRAP_ADMIN_ENABLED"]
    PICO_BOOTSTRAP_ADMIN_USERNAME = $(if ([string]::IsNullOrWhiteSpace([string]$envs["PICO_BOOTSTRAP_ADMIN_USERNAME"])) { "not-configured" } else { "configured" })
}
Save-Diagnostic "config-safe.json" ($safe | ConvertTo-Json -Depth 3)
Save-Diagnostic "dte-config-readiness.txt" ((@(
    "DTE_CONFIG_READY=$dteConfigReady",
    "DTE_BASE_URL_STATUS=$(if ($dteBaseUrlLooksReady) { 'configured' } else { 'placeholder-or-invalid' })",
    "DTE_TOKEN_STATUS=$(if ($dteTokenLooksReady) { 'configured' } else { 'placeholder-or-invalid' })"
) -join "`n"))

$appUrl = Get-AppUrl
$backendPort = if ([string]::IsNullOrWhiteSpace([string]$envs["BACKEND_HTTP_PORT"])) { "8000" } else { [string]$envs["BACKEND_HTTP_PORT"] }
function Read-DiagnosticHttpBody {
    param($Response)
    if ($null -eq $Response) {
        return ""
    }
    try {
        if ($Response.PSObject.Properties.Name -contains "Content") {
            return [string]$Response.Content
        }
    } catch {
    }
    try {
        $stream = $Response.GetResponseStream()
        if ($stream) {
            $reader = New-Object System.IO.StreamReader($stream)
            try {
                return [string]$reader.ReadToEnd()
            } finally {
                $reader.Dispose()
            }
        }
    } catch {
    }
    return ""
}
function Convert-DiagnosticHeaders {
    param($Headers)
    if ($null -eq $Headers) {
        return ""
    }
    $lines = @()
    try {
        if ($Headers -is [System.Net.WebHeaderCollection]) {
            foreach ($key in @($Headers.AllKeys)) {
                $lines += ("{0}={1}" -f $key, [string]$Headers[$key])
            }
        } elseif ($Headers -is [System.Collections.IDictionary]) {
            foreach ($key in @($Headers.Keys)) {
                $lines += ("{0}={1}" -f $key, [string]$Headers[$key])
            }
        }
    } catch {
    }
    return ($lines -join "; ")
}
function Get-HealthStatusDetailed {
    param([Parameter(Mandatory = $true)][string]$Uri)
    $status = "error"
    $description = ""
    $headers = ""
    $body = ""
    $errorText = ""
    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
        $status = [string]$response.StatusCode
        $description = [string]$response.StatusDescription
        $headers = Convert-DiagnosticHeaders -Headers $response.Headers
        $body = Read-DiagnosticHttpBody -Response $response
    } catch {
        $errorText = [string]$_.Exception.Message
        $response = $_.Exception.Response
        if ($response) {
            try { $status = [string][int]$response.StatusCode } catch { }
            try { $description = [string]$response.StatusDescription } catch { }
            $headers = Convert-DiagnosticHeaders -Headers $response.Headers
            $body = Read-DiagnosticHttpBody -Response $response
        }
    }
    return ((@(
        "url=$Uri",
        "status=$status",
        "description=$description",
        "headers=$headers",
        "body=$body",
        "error=$errorText"
    ) -join "`n"))
}
$rootHealth = Get-HealthStatusDetailed -Uri $appUrl
$liveHealth = Get-HealthStatusDetailed -Uri ($appUrl + "/api/health/live/")
$readyHealth = Get-HealthStatusDetailed -Uri ($appUrl + "/api/health/ready/")
$backendLiveHealth = Get-HealthStatusDetailed -Uri "http://127.0.0.1:$backendPort/api/health/live/"
$backendReadyHealth = Get-HealthStatusDetailed -Uri "http://127.0.0.1:$backendPort/api/health/ready/"
Save-Diagnostic "health.txt" ((@(
    "ROOT_BEGIN",
    $rootHealth,
    "ROOT_END",
    "CADDY_LIVE_BEGIN",
    $liveHealth,
    "CADDY_LIVE_END",
    "CADDY_READY_BEGIN",
    $readyHealth,
    "CADDY_READY_END",
    "BACKEND_LIVE_BEGIN",
    $backendLiveHealth,
    "BACKEND_LIVE_END",
    "BACKEND_READY_BEGIN",
    $backendReadyHealth,
    "BACKEND_READY_END"
) -join "`n"))

foreach ($log in Get-ChildItem (Get-LogsDir) -Filter "*.log" -ErrorAction SilentlyContinue) {
    Save-Diagnostic "log-$($log.Name).txt" ((Get-Content -LiteralPath $log.FullName -Tail 300) -join "`n")
}

$caddyLogs = Get-ChildItem (Get-LogsDir) -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*Caddy*" -or $_.Name -like "*caddy*" } |
    Sort-Object LastWriteTime -Descending
foreach ($log in $caddyLogs) {
    Save-Diagnostic "caddy-wrapper-$($log.Name).txt" ((Get-Content -LiteralPath $log.FullName -Tail 300 -ErrorAction SilentlyContinue) -join "`n")
}

$autoTlsNeedles = @(
    "automatic TLS certificate management",
    "installing root certificate",
    "failed to install root certificate",
    "automatic HTTP->HTTPS redirects",
    "enabling automatic HTTP->HTTPS redirects",
    "HTTP/2 skipped because it requires TLS",
    "HTTP/3 listener"
)
$autoTlsFindings = @()
foreach ($log in $caddyLogs) {
    $tail = ((Get-Content -LiteralPath $log.FullName -Tail 500 -ErrorAction SilentlyContinue | ForEach-Object { [string]$_ }) -join "`n")
    foreach ($needle in $autoTlsNeedles) {
        if ($tail -match [regex]::Escape($needle)) {
            $autoTlsFindings += ("{0}:{1}" -f $log.Name, $needle)
        }
    }
}
Save-Diagnostic "caddy-auto-tls-evidence.txt" ((@(
    "automatic_tls_or_root_cert_logs=$(if ($autoTlsFindings.Count -gt 0) { 'present' } else { 'absent' })",
    (($autoTlsFindings | Select-Object -Unique) -join "`n")
) -join "`n"))

$zip = Join-Path (Get-DiagnosticsDir) "PicoDeGallo-Native-Diagnostico-$stamp.zip"
Compress-Archive -Path (Join-Path $root "*") -DestinationPath $zip -Force
Remove-Item -LiteralPath $root -Recurse -Force
Write-SafeHost "Diagnostico generado: $zip"
