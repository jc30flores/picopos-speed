$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

Assert-Admin

function Get-RequiredEnvValue {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Map,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $value = [string]$Map[$Name]
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Falta $Name en configuracion nativa."
    }
    return $value
}

function Get-NativeLogPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    New-DirectorySafe (Get-LogsDir)
    return (Join-Path (Get-LogsDir) $Name)
}

function Write-InstallLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$LogName = "install-services.log"
    )

    $line = "[{0}] {1}" -f (Get-Date -Format o), (Protect-Text $Message)
    Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value $line -Encoding UTF8
}

function Format-CommandForLog {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    $parts = @($FilePath) + $ArgumentList
    $quoted = foreach ($part in $parts) {
        $text = [string]$part
        if ($text -match '\s') {
            '"' + $text.Replace('"', '\"') + '"'
        } else {
            $text
        }
    }
    return ($quoted -join " ")
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][string]$LogName,
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{},
        [switch]$ReturnStdout
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "No existe ejecutable requerido: $FilePath"
    }

    $logPath = Get-NativeLogPath $LogName
    $stdout = Join-Path (Get-LogsDir) ("{0}.stdout.tmp" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path (Get-LogsDir) ("{0}.stderr.tmp" -f ([Guid]::NewGuid().ToString("N")))
    $oldEnvironment = @{}
    $exitCode = 0

    Write-InstallLog -LogName $LogName -Message ("RUN " + (Format-CommandForLog -FilePath $FilePath -ArgumentList $ArgumentList))

    try {
        foreach ($name in $Environment.Keys) {
            $oldEnvironment[$name] = [Environment]::GetEnvironmentVariable([string]$name, "Process")
            [Environment]::SetEnvironmentVariable([string]$name, [string]$Environment[$name], "Process")
        }

        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            Push-Location $WorkingDirectory
        }

        try {
            & $FilePath @ArgumentList > $stdout 2> $stderr
            $exitCode = $LASTEXITCODE
        } catch {
            Write-InstallLog -LogName $LogName -Message ("FAILED_TO_LAUNCH " + $_.Exception.Message)
            throw
        } finally {
            if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
                Pop-Location
            }
        }
    } finally {
        foreach ($name in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable([string]$name, $oldEnvironment[$name], "Process")
        }
    }

    $stdoutText = ""
    $stderrText = ""
    if (Test-Path -LiteralPath $stdout -PathType Leaf) {
        $stdoutText = Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stdoutText)) {
            Add-Content -LiteralPath $logPath -Value (Protect-Text $stdoutText) -Encoding UTF8
        }
    }
    if (Test-Path -LiteralPath $stderr -PathType Leaf) {
        $stderrText = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
            Add-Content -LiteralPath $logPath -Value (Protect-Text $stderrText) -Encoding UTF8
        }
    }

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    Write-InstallLog -LogName $LogName -Message ("EXIT_CODE " + $exitCode)
    if ($exitCode -ne 0) {
        throw "Comando fallo con codigo $exitCode. Revise $logPath"
    }

    if ($ReturnStdout) {
        return $stdoutText
    }
}

function Render-Template {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][hashtable]$Tokens
    )

    $content = Get-Content -LiteralPath $Source -Raw
    foreach ($key in $Tokens.Keys) {
        $content = $content.Replace("{{$key}}", [string]$Tokens[$key])
    }
    Set-Content -LiteralPath $Destination -Value $content -Encoding UTF8
}

function Get-ServiceWrapperPath {
    param([Parameter(Mandatory = $true)][string]$ServiceId)
    return (Join-Path (Join-Path $Script:ProgramFilesDir "services") "$ServiceId.exe")
}

function Invoke-WinSWCommand {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [Parameter(Mandatory = $true)][string]$Command
    )

    $wrapper = Get-ServiceWrapperPath -ServiceId $ServiceId
    Invoke-LoggedCommand `
        -FilePath $wrapper `
        -ArgumentList @($Command) `
        -LogName "service-install.log"
}

function Wait-ServiceStatus {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [Parameter(Mandatory = $true)][string]$DesiredStatus,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $service = Get-ServiceSafe $ServiceId
        if ($service -and ([string]$service.Status) -eq $DesiredStatus) {
            Write-InstallLog "SERVICE_STATUS $ServiceId $DesiredStatus"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    $current = Get-ServiceSafe $ServiceId
    $status = if ($current) { [string]$current.Status } else { "not-installed" }
    throw "Servicio $ServiceId no llego a estado $DesiredStatus. Estado actual: $status"
}

function Start-WinSWService {
    param([Parameter(Mandatory = $true)][string]$ServiceId)

    $service = Get-ServiceSafe $ServiceId
    if (-not $service) {
        throw "Servicio requerido no instalado: $ServiceId"
    }
    if ($service.Status -eq "Running") {
        Write-InstallLog "SERVICE_ALREADY_RUNNING $ServiceId"
        if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
            Write-InstallLog -LogName "postgres-service.log" -Message "SERVICE_ALREADY_RUNNING $ServiceId"
        }
        return
    }

    try {
        Invoke-WinSWCommand -ServiceId $ServiceId -Command "start"
    } catch {
        $service = Get-ServiceSafe $ServiceId
        if (-not $service -or $service.Status -ne "Running") {
            throw
        }
    }

    Wait-ServiceStatus -ServiceId $ServiceId -DesiredStatus "Running" -TimeoutSeconds 90
    if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
        Write-InstallLog -LogName "postgres-service.log" -Message "SERVICE_RUNNING $ServiceId"
    }
    Write-SafeHost "Servicio iniciado: $ServiceId"
}

function Assert-AllServicesInstalled {
    foreach ($serviceId in $Script:Services) {
        if (-not (Get-ServiceSafe $serviceId)) {
            throw "Servicio requerido no instalado: $serviceId"
        }
    }
}

function Assert-AllServicesRunning {
    foreach ($serviceId in $Script:Services) {
        Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Running" -TimeoutSeconds 30
    }
}

function Install-WinSWServices {
    param([Parameter(Mandatory = $true)][hashtable]$Tokens)

    $serviceDir = Join-Path $Script:ProgramFilesDir "services"
    $templateDir = Join-Path $serviceDir "templates"
    $winswSource = Join-Path $serviceDir "winsw.exe"

    if (-not (Test-Path -LiteralPath $winswSource -PathType Leaf)) {
        throw "No existe WinSW en $winswSource"
    }
    if (-not (Test-Path -LiteralPath $templateDir -PathType Container)) {
        throw "No existen templates de servicios en $templateDir"
    }

    foreach ($serviceId in $Script:Services) {
        $template = Join-Path $templateDir "$serviceId.xml"
        if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
            throw "Falta template WinSW para $serviceId"
        }

        $targetXml = Join-Path $serviceDir "$serviceId.xml"
        $targetExe = Get-ServiceWrapperPath -ServiceId $serviceId
        $existingService = Get-ServiceSafe $serviceId

        if ($existingService -and $existingService.Status -eq "Running") {
            Write-InstallLog -LogName "service-install.log" -Message "SERVICE_STOP_FOR_UPDATE $serviceId"
            Stop-Service -Name $serviceId -ErrorAction Stop
            Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Stopped" -TimeoutSeconds 90
        }

        Render-Template -Source $template -Destination $targetXml -Tokens $Tokens
        if ((Get-Content -LiteralPath $targetXml -Raw).Contains("{{")) {
            throw "XML WinSW renderizado contiene placeholders sin resolver: $targetXml"
        }
        Copy-Item -LiteralPath $winswSource -Destination $targetExe -Force

        if (Get-ServiceSafe $serviceId) {
            Write-InstallLog "SERVICE_ALREADY_INSTALLED $serviceId"
            Write-InstallLog -LogName "service-install.log" -Message "SERVICE_XML_UPDATED $serviceId"
            Write-SafeHost "Servicio ya instalado: $serviceId"
        } else {
            Invoke-WinSWCommand -ServiceId $serviceId -Command "install"
            Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Stopped" -TimeoutSeconds 30
            Write-SafeHost "Servicio instalado: $serviceId"
        }
    }

    Assert-AllServicesInstalled
}

function Quote-PostgresIdentifier {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ('"' + $Value.Replace('"', '""') + '"')
}

function Quote-PostgresLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ("'" + $Value.Replace("'", "''") + "'")
}

function Initialize-PostgresDataDirectory {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $initdb = Join-Path $postgresBin "initdb.exe"

    if (-not (Test-Path -LiteralPath $initdb -PathType Leaf)) {
        throw "No existe initdb.exe en runtime PostgreSQL nativo."
    }
    if (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION") -PathType Leaf) {
        Write-InstallLog "POSTGRES_DATA_EXISTS $dataDir"
        return
    }

    $existing = Get-ChildItem -LiteralPath $dataDir -Force -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        throw "El directorio de datos PostgreSQL existe pero no contiene PG_VERSION: $dataDir"
    }

    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"
    $dbPassword = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PASSWORD"
    $pwFile = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-pg-" + [Guid]::NewGuid().ToString("N") + ".pw")

    try {
        Set-Content -LiteralPath $pwFile -Value $dbPassword -Encoding ASCII
        Invoke-LoggedCommand `
            -FilePath $initdb `
            -ArgumentList @("-D", $dataDir, "-E", "UTF8", "--locale=C", "--username=$dbUser", "--pwfile=$pwFile", "--auth=scram-sha-256") `
            -LogName "postgres-init.log"
    } finally {
        Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
    }
}

function Set-PostgresConfigValue {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "No existe archivo de configuracion PostgreSQL: $ConfigPath"
    }

    $escaped = [regex]::Escape($Key)
    $line = "$Key = $Value"
    $content = Get-Content -LiteralPath $ConfigPath -Encoding UTF8
    $updated = $false
    $newContent = @(foreach ($item in $content) {
        if ($item -match "^\s*#?\s*$escaped\s*=") {
            $updated = $true
            $line
        } else {
            $item
        }
    })
    if (-not $updated) {
        $newContent += $line
    }
    Set-Content -LiteralPath $ConfigPath -Value $newContent -Encoding UTF8
}

function Configure-PostgresDataDirectory {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $config = Join-Path $dataDir "postgresql.conf"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"

    Set-PostgresConfigValue -ConfigPath $config -Key "port" -Value $dbPort
    Set-PostgresConfigValue -ConfigPath $config -Key "listen_addresses" -Value "'127.0.0.1'"
    Write-InstallLog -LogName "postgres-init.log" -Message "POSTGRES_CONFIGURED port=$dbPort listen_addresses=127.0.0.1"
}

function Wait-PostgresReady {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $pgIsReady = Join-Path $postgresBin "pg_isready.exe"
    if (-not (Test-Path -LiteralPath $pgIsReady -PathType Leaf)) {
        throw "Falta pg_isready.exe en runtime PostgreSQL nativo."
    }

    $dbHost = Get-RequiredEnvValue -Map $EnvMap -Name "DB_HOST"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"
    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"

    for ($i = 0; $i -lt 60; $i++) {
        & $pgIsReady -h $dbHost -p $dbPort -U $dbUser | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-InstallLog "POSTGRES_READY $dbHost`:$dbPort"
            Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_READY $dbHost`:$dbPort"
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "PostgreSQL no quedo listo para configuracion inicial."
}

function Ensure-ApplicationDatabase {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $psql = Join-Path $postgresBin "psql.exe"
    $createdb = Join-Path $postgresBin "createdb.exe"
    foreach ($tool in @($psql, $createdb)) {
        if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
            throw "Falta herramienta PostgreSQL: $tool"
        }
    }

    $dbHost = Get-RequiredEnvValue -Map $EnvMap -Name "DB_HOST"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"
    $dbName = Get-RequiredEnvValue -Map $EnvMap -Name "DB_NAME"
    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"
    $dbPassword = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PASSWORD"
    $pgEnv = @{ PGPASSWORD = $dbPassword }
    $roleSql = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-role-" + [Guid]::NewGuid().ToString("N") + ".sql")

    try {
        $roleNameLiteral = Quote-PostgresLiteral -Value $dbUser
        $roleNameIdentifier = Quote-PostgresIdentifier -Value $dbUser
        $passwordLiteral = Quote-PostgresLiteral -Value $dbPassword
        @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = $roleNameLiteral) THEN
        CREATE ROLE $roleNameIdentifier WITH LOGIN PASSWORD $passwordLiteral;
    ELSE
        ALTER ROLE $roleNameIdentifier WITH LOGIN PASSWORD $passwordLiteral;
    END IF;
END
`$`$;
"@ | Set-Content -LiteralPath $roleSql -Encoding UTF8

        Invoke-LoggedCommand `
            -FilePath $psql `
            -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-f", $roleSql) `
            -LogName "db-setup.log" `
            -Environment $pgEnv
    } finally {
        Remove-Item -LiteralPath $roleSql -Force -ErrorAction SilentlyContinue
    }

    $escapedDbName = $dbName.Replace("'", "''")
    $exists = Invoke-LoggedCommand `
        -FilePath $psql `
        -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-tAc", "SELECT 1 FROM pg_database WHERE datname = '$escapedDbName';") `
        -LogName "db-setup.log" `
        -Environment $pgEnv `
        -ReturnStdout

    if (($exists -join "").Trim() -ne "1") {
        Invoke-LoggedCommand `
            -FilePath $createdb `
            -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-O", $dbUser, $dbName) `
            -LogName "db-setup.log" `
            -Environment $pgEnv
    }
}

function Render-Caddyfile {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $template = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile.template"
    $caddyfile = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile"
    if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
        throw "Falta Caddyfile.template en runtime nativo."
    }

    $bind = [string]$EnvMap["APP_BIND_ADDRESS"]
    if ([string]::IsNullOrWhiteSpace($bind)) { $bind = "127.0.0.1" }
    $port = [string]$EnvMap["APP_HTTP_PORT"]
    if ([string]::IsNullOrWhiteSpace($port)) { $port = "9282" }

    (Get-Content -LiteralPath $template -Raw).
        Replace("{{APP_BIND_ADDRESS}}", $bind).
        Replace("{{APP_HTTP_PORT}}", $port).
        Replace("{{PROGRAM_FILES_DIR}}", $Script:ProgramFilesDir.Replace("\", "/")).
        Replace("{{PROGRAM_DATA_DIR}}", $Script:ProgramDataDir.Replace("\", "/")) |
        Set-Content -LiteralPath $caddyfile -Encoding UTF8

    Write-InstallLog "CADDYFILE_RENDERED $caddyfile"
}

function Validate-EmbeddedPythonImports {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("-c", "import django, waitress, psycopg2, requests; print('Python runtime OK')") `
        -LogName "python-runtime.log"
}

function Get-DjangoEnvironment {
    return @{
        DJANGO_ENV_FILE = (Get-EnvPath)
        DOTENV_OVERRIDE = "false"
        DJANGO_SETTINGS_MODULE = "config.settings"
        PYTHONUNBUFFERED = "1"
    }
}

function Run-DjangoSetup {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "No existe python.exe en runtime nativo."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $backend "manage.py") -PathType Leaf)) {
        throw "No existe backend Django en $backend"
    }

    $djangoEnv = Get-DjangoEnvironment

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "check_runtime_config", "--strict") `
        -WorkingDirectory $backend `
        -Environment $djangoEnv `
        -LogName "check-runtime-config.log"

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "migrate", "--noinput") `
        -WorkingDirectory $backend `
        -Environment $djangoEnv `
        -LogName "migrate.log"

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "collectstatic", "--noinput") `
        -WorkingDirectory $backend `
        -Environment $djangoEnv `
        -LogName "collectstatic.log"
}

function Run-InitialAdminBootstrap {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "bootstrap_initial_admin") `
        -WorkingDirectory $backend `
        -Environment (Get-DjangoEnvironment) `
        -LogName "bootstrap-admin.log"
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            $status = [int]$response.StatusCode
            if ($status -ge 200 -and $status -lt 300) {
                Write-InstallLog -LogName "healthcheck.log" -Message "HTTP_OK $Name $Uri status=$status"
                return
            }
            $lastError = "status=$status"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-InstallLog -LogName "healthcheck.log" -Message "HTTP_FAILED $Name $Uri $lastError"
    throw "Validacion HTTP fallo para $Name ($Uri): $lastError"
}

function Start-ApplicationServices {
    Start-WinSWService -ServiceId "PicoDeGallo-Backend"
    Wait-HttpOk -Name "backend-ready-direct" -Uri "http://127.0.0.1:8000/api/health/ready/" -TimeoutSeconds 120

    Start-WinSWService -ServiceId "PicoDeGallo-DTE-Worker"
    Start-WinSWService -ServiceId "PicoDeGallo-DTE-Monitor"
    Start-WinSWService -ServiceId "PicoDeGallo-Caddy"
}

function Validate-PostInstall {
    $appUrl = Get-AppUrl
    Wait-HttpOk -Name "caddy-root" -Uri $appUrl -TimeoutSeconds 120
    Wait-HttpOk -Name "health-live" -Uri "$appUrl/api/health/live/" -TimeoutSeconds 120
    Wait-HttpOk -Name "health-ready" -Uri "$appUrl/api/health/ready/" -TimeoutSeconds 120
    Assert-AllServicesRunning
}

foreach ($dir in @("config", "media", "static", "dte_logs", "backups", "diagnostics", "logs", "postgres\data")) {
    New-DirectorySafe (Join-Path $Script:ProgramDataDir $dir)
}

Write-InstallLog "INSTALL_SERVICES_BEGIN ProgramFiles=$Script:ProgramFilesDir ProgramData=$Script:ProgramDataDir"

if (-not (Test-Path -LiteralPath (Get-EnvPath) -PathType Leaf)) {
    & "$PSScriptRoot\init-env.ps1"
}

$envs = Read-NativeEnv
Test-DteEnv | Out-Null

$tokens = @{
    PROGRAM_FILES_DIR = $Script:ProgramFilesDir
    PROGRAM_DATA_DIR = $Script:ProgramDataDir
    POSTGRES_BIN_DIR = (Join-Path $Script:ProgramFilesDir "postgres\bin")
    PYTHON_EXE = (Join-Path $Script:ProgramFilesDir "python\python.exe")
    BACKEND_DIR = (Join-Path $Script:ProgramFilesDir "backend")
    ENV_FILE = (Get-EnvPath)
    CADDY_EXE = (Join-Path $Script:ProgramFilesDir "caddy\caddy.exe")
    APP_HTTP_PORT = if ([string]::IsNullOrWhiteSpace([string]$envs["APP_HTTP_PORT"])) { "9282" } else { [string]$envs["APP_HTTP_PORT"] }
    APP_BIND_ADDRESS = if ([string]::IsNullOrWhiteSpace([string]$envs["APP_BIND_ADDRESS"])) { "127.0.0.1" } else { [string]$envs["APP_BIND_ADDRESS"] }
}

Validate-EmbeddedPythonImports
Initialize-PostgresDataDirectory -EnvMap $envs
Configure-PostgresDataDirectory -EnvMap $envs
Render-Caddyfile -EnvMap $envs
Install-WinSWServices -Tokens $tokens
Start-WinSWService -ServiceId "PicoDeGallo-PostgreSQL"
Wait-PostgresReady -EnvMap $envs
Ensure-ApplicationDatabase -EnvMap $envs
Run-DjangoSetup
Run-InitialAdminBootstrap
Start-ApplicationServices
Validate-PostInstall

foreach ($svc in $Script:Services) {
    Write-SafeHost "Servicio listo: $svc"
}

Write-InstallLog "INSTALL_SERVICES_SUCCESS"
