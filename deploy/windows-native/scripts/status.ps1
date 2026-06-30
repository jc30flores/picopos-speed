$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

function Test-TcpPort {
    param([string]$HostName = "127.0.0.1", [int]$Port = 9282)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds(2))) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Get-HttpStatus {
    param([Parameter(Mandatory = $true)][string]$Uri)
    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
        return [string]$response.StatusCode
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            return [string][int]$_.Exception.Response.StatusCode
        }
        return "error"
    }
}

function Get-InstalledVersion {
    $versionPath = Join-Path $Script:ProgramFilesDir "version.json"
    if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
        return "missing"
    }
    try {
        $json = Get-Content -LiteralPath $versionPath -Raw -ErrorAction Stop | ConvertFrom-Json
        if ($json.version) {
            return [string]$json.version
        }
    } catch {
        return "error"
    }
    return "unknown"
}

function Get-PicoServiceAccountStatus {
    $accountName = $Script:PicoServiceAccountName
    if (Get-Command Get-LocalUser -ErrorAction SilentlyContinue) {
        try {
            $user = Get-LocalUser -Name $accountName -ErrorAction Stop
            $expires = if ($null -eq $user.PasswordExpires) { "never" } else { [string]$user.PasswordExpires }
            $never = if ($null -eq $user.PasswordExpires) { "true" } else { "false" }
            return "exists Enabled=$($user.Enabled) PasswordExpires=$expires PasswordNeverExpires=$never"
        } catch {
        }
    }
    try {
        $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $accountName)
        $null = $user.Name
        $flags = [int]$user.UserFlags.Value
        $never = (($flags -band 0x10000) -ne 0)
        return "exists PasswordNeverExpires=$never provider=ADSI"
    } catch {
        return "missing"
    }
}

function Get-PostgresDataStatus {
    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $facts = foreach ($fileName in @("PG_VERSION", "postgresql.conf", "pg_hba.conf")) {
        "$fileName=$(if (Test-Path -LiteralPath (Join-Path $dataDir $fileName) -PathType Leaf) { 'present' } else { 'missing' })"
    }
    return ($facts -join " ")
}

function Get-ServiceFileStatus {
    $serviceDir = Join-Path $Script:ProgramFilesDir "services"
    $facts = foreach ($svc in $Script:Services) {
        $xml = Join-Path $serviceDir "$svc.xml"
        $exe = Join-Path $serviceDir "$svc.exe"
        "$svc.xml=$(if (Test-Path -LiteralPath $xml -PathType Leaf) { 'present' } else { 'missing' }) $svc.exe=$(if (Test-Path -LiteralPath $exe -PathType Leaf) { 'present' } else { 'missing' })"
    }
    return ($facts -join "; ")
}

function Get-CaddyfileStatus {
    $caddyfile = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile"
    return $(if (Test-Path -LiteralPath $caddyfile -PathType Leaf) { "present" } else { "missing" })
}

function Get-LastRunAsExitCode {
    $runAsDir = Join-Path (Get-LogsDir) "runas"
    $latest = Get-ChildItem -LiteralPath $runAsDir -Filter "*.exitcode" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) {
        return "none"
    }
    $value = (Get-Content -LiteralPath $latest.FullName -Raw -ErrorAction SilentlyContinue).Trim()
    return "$value path=$($latest.FullName)"
}

function Get-PostgresXmlMode {
    $xmlPath = Join-Path (Join-Path $Script:ProgramFilesDir "services") "PicoDeGallo-PostgreSQL.xml"
    if (-not (Test-Path -LiteralPath $xmlPath -PathType Leaf)) {
        return "missing"
    }
    $content = Get-Content -LiteralPath $xmlPath -Raw -ErrorAction SilentlyContinue
    if ($content -match "postgres\.exe") {
        return "postgres.exe"
    }
    if ($content -match "pg_ctl") {
        return "legacy-pg_ctl"
    }
    return "unknown"
}

function Get-PostgresXmlServiceAccountStatus {
    $xmlPath = Join-Path (Join-Path $Script:ProgramFilesDir "services") "PicoDeGallo-PostgreSQL.xml"
    if (-not (Test-Path -LiteralPath $xmlPath -PathType Leaf)) {
        return "missing"
    }
    $content = Get-Content -LiteralPath $xmlPath -Raw -ErrorAction SilentlyContinue
    if ($content -notmatch "<serviceaccount>") {
        return "absent"
    }
    if ($content -match "<password>") {
        return "present-with-password-field"
    }
    if ($content -match [regex]::Escape($Script:PicoServiceAccountName)) {
        return "present-no-password"
    }
    return "present-unknown-user"
}

function Get-PostgresForegroundRunAs {
    $logPath = Join-Path (Get-LogsDir) "postgres-service.log"
    if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
        return "unknown"
    }
    $content = Get-Content -LiteralPath $logPath -Tail 200 -ErrorAction SilentlyContinue
    if (($content -join "`n") -match "POSTGRES_FOREGROUND_TEST_RUN_AS\s+$([regex]::Escape($Script:PicoServiceAccountName))") {
        return $Script:PicoServiceAccountName
    }
    return "unknown"
}

function Show-PostgresErrorTail {
    foreach ($logName in @(
        "postgres-foreground-test.err.log",
        "postgres-foreground-test.out.log",
        "PicoDeGallo-PostgreSQL.wrapper.log",
        "PicoDeGallo-PostgreSQL.err.log",
        "PicoDeGallo-PostgreSQL.out.log",
        "postgres-service.log"
    )) {
        $path = Join-Path (Get-LogsDir) $logName
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Write-SafeHost "POSTGRES_LOG_TAIL_BEGIN $logName"
            Get-Content -LiteralPath $path -Tail 40 -ErrorAction SilentlyContinue |
                ForEach-Object { Write-SafeHost ([string]$_) }
            Write-SafeHost "POSTGRES_LOG_TAIL_END $logName"
        }
    }
}

$envs = Read-NativeEnv
$appUrl = Get-AppUrl
$port = "9282"
if ($envs.Contains("APP_HTTP_PORT") -and -not [string]::IsNullOrWhiteSpace([string]$envs["APP_HTTP_PORT"])) {
    $port = [string]$envs["APP_HTTP_PORT"]
}
$dbHost = if ([string]::IsNullOrWhiteSpace([string]$envs["DB_HOST"])) { "127.0.0.1" } else { [string]$envs["DB_HOST"] }
$dbPort = if ([string]::IsNullOrWhiteSpace([string]$envs["DB_PORT"])) { 5432 } else { [int]$envs["DB_PORT"] }

Write-SafeHost "URL: $appUrl"
Write-SafeHost "VERSION=$(Get-InstalledVersion)"
Write-SafeHost "PICO_SERVICE_ACCOUNT=$(Get-PicoServiceAccountStatus)"
Write-SafeHost "POSTGRES_DATA=$(Get-PostgresDataStatus)"
Write-SafeHost "SERVICE_FILES=$(Get-ServiceFileStatus)"
Write-SafeHost "CADDYFILE=$(Get-CaddyfileStatus)"
Write-SafeHost "RUNAS_LAST_EXITCODE=$(Get-LastRunAsExitCode)"
Write-SafeHost "POSTGRES_XML_EXECUTABLE=$(Get-PostgresXmlMode)"
Write-SafeHost "POSTGRES_XML_SERVICEACCOUNT=$(Get-PostgresXmlServiceAccountStatus)"
Write-SafeHost "POSTGRES_FOREGROUND_TEST_RUN_AS=$(Get-PostgresForegroundRunAs)"
foreach ($svc in $Script:Services) {
    $service = Get-ServiceSafe $svc
    if ($service) {
        Write-SafeHost "$svc=$($service.Status) StartName=$(Get-ServiceStartNameSafe -Name $svc)"
    } else {
        Write-SafeHost "$svc=not-installed"
    }
}

$liveUrl = $appUrl + "/api/health/live/"
$readyUrl = $appUrl + "/api/health/ready/"
Write-SafeHost "PORT_$dbPort=$(if (Test-TcpPort -HostName $dbHost -Port ([int]$dbPort)) { 'listening' } else { 'closed' })"
Write-SafeHost "PORT_8000=$(if (Test-TcpPort -Port 8000) { 'listening' } else { 'closed' })"
Write-SafeHost "PORT_$port=$(if (Test-TcpPort -Port ([int]$port)) { 'listening' } else { 'closed' })"
Write-SafeHost "BACKEND_HEALTH_READY=$(Get-HttpStatus -Uri 'http://127.0.0.1:8000/api/health/ready/')"
Write-SafeHost "HEALTH_LIVE=$(Get-HttpStatus -Uri $liveUrl)"
Write-SafeHost "HEALTH_READY=$(Get-HttpStatus -Uri $readyUrl)"
Write-SafeHost "DTE_BACKGROUND_MODE=$($envs['DTE_BACKGROUND_MODE'])"
Write-SafeHost "DTE_BASE_URL=$(if ($envs['DTE_BASE_URL'] -like 'replace-with-*') { 'placeholder' } else { 'configured' })"
Write-SafeHost "DTE_API_TOKEN=$(if ($envs['DTE_API_TOKEN'] -like 'replace-with-*') { 'placeholder' } else { 'configured' })"
Write-SafeHost "BOOTSTRAP_ADMIN_ENABLED=$(if ($envs['PICO_BOOTSTRAP_ADMIN_ENABLED'] -eq 'true') { 'yes' } else { 'no' })"
Write-SafeHost "BOOTSTRAP_ADMIN_USERNAME=$(if ([string]::IsNullOrWhiteSpace([string]$envs['PICO_BOOTSTRAP_ADMIN_USERNAME'])) { 'not-configured' } else { 'configured' })"
Show-PostgresErrorTail
$installErrorLog = Join-Path (Get-LogsDir) "install-services-error.log"
if (Test-Path -LiteralPath $installErrorLog -PathType Leaf) {
    Write-SafeHost "INSTALL_SERVICES_ERROR_TAIL_BEGIN"
    Get-Content -LiteralPath $installErrorLog -Tail 80 -ErrorAction SilentlyContinue |
        ForEach-Object { Write-SafeHost ([string]$_) }
    Write-SafeHost "INSTALL_SERVICES_ERROR_TAIL_END"
}
