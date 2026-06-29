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

    foreach ($template in Get-ChildItem -LiteralPath $templateDir -Filter "*.xml" -File) {
        $serviceId = [System.IO.Path]::GetFileNameWithoutExtension($template.Name)
        $targetXml = Join-Path $serviceDir "$serviceId.xml"
        $targetExe = Join-Path $serviceDir "$serviceId.exe"

        Render-Template -Source $template.FullName -Destination $targetXml -Tokens $Tokens
        Copy-Item -LiteralPath $winswSource -Destination $targetExe -Force

        if (Get-ServiceSafe $serviceId) {
            Write-SafeHost "Servicio ya instalado: $serviceId"
            continue
        }

        & $targetExe install
        if ($LASTEXITCODE -ne 0) {
            throw "WinSW no pudo instalar $serviceId."
        }
        Write-SafeHost "Servicio instalado: $serviceId"
    }
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
        return
    }

    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"
    $dbPassword = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PASSWORD"
    $pwFile = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-pg-" + [Guid]::NewGuid().ToString("N") + ".pw")

    try {
        Set-Content -LiteralPath $pwFile -Value $dbPassword -Encoding ASCII
        & $initdb -D $dataDir -E UTF8 --locale=C "--username=$dbUser" "--pwfile=$pwFile" "--auth=scram-sha-256"
        if ($LASTEXITCODE -ne 0) {
            throw "initdb fallo."
        }
    } finally {
        Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
    }
}

function Start-PostgresForSetup {
    $service = Get-ServiceSafe "PicoDeGallo-PostgreSQL"
    if (-not $service) {
        throw "PicoDeGallo-PostgreSQL no esta instalado."
    }
    if ($service.Status -ne "Running") {
        Start-Service "PicoDeGallo-PostgreSQL"
    }
}

function Wait-PostgresReady {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $pgIsReady = Join-Path $postgresBin "pg_isready.exe"
    if (-not (Test-Path -LiteralPath $pgIsReady -PathType Leaf)) {
        Start-Sleep -Seconds 5
        return
    }

    $dbHost = Get-RequiredEnvValue -Map $EnvMap -Name "DB_HOST"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"
    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"

    for ($i = 0; $i -lt 30; $i++) {
        & $pgIsReady -h $dbHost -p $dbPort -U $dbUser | Out-Null
        if ($LASTEXITCODE -eq 0) {
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
    $escapedDbName = $dbName.Replace("'", "''")
    $oldPgPassword = $env:PGPASSWORD

    try {
        $env:PGPASSWORD = $dbPassword
        $exists = & $psql -h $dbHost -p $dbPort -U $dbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$escapedDbName';"
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudo consultar PostgreSQL."
        }
        if (($exists -join "").Trim() -ne "1") {
            & $createdb -h $dbHost -p $dbPort -U $dbUser $dbName
            if ($LASTEXITCODE -ne 0) {
                throw "No se pudo crear base de datos $dbName."
            }
        }
    } finally {
        $env:PGPASSWORD = $oldPgPassword
    }
}

function Render-Caddyfile {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $template = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile.template"
    $caddyfile = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile"
    if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
        return
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
}

function Run-DjangoSetup {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "No existe python.exe en runtime nativo."
    }

    $oldEnvFile = $env:DJANGO_ENV_FILE
    try {
        $env:DJANGO_ENV_FILE = Get-EnvPath
        Push-Location $backend
        & $python manage.py check_runtime_config --strict
        if ($LASTEXITCODE -ne 0) { throw "check_runtime_config fallo." }
        & $python manage.py migrate --noinput
        if ($LASTEXITCODE -ne 0) { throw "migrate fallo." }
        & $python manage.py collectstatic --noinput
        if ($LASTEXITCODE -ne 0) { throw "collectstatic fallo." }
    } finally {
        Pop-Location
        $env:DJANGO_ENV_FILE = $oldEnvFile
    }
}

foreach ($dir in @("config", "media", "static", "dte_logs", "backups", "diagnostics", "logs", "postgres\data")) {
    New-DirectorySafe (Join-Path $Script:ProgramDataDir $dir)
}

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
}

Initialize-PostgresDataDirectory -EnvMap $envs
Render-Caddyfile -EnvMap $envs
Install-WinSWServices -Tokens $tokens
Start-PostgresForSetup
Wait-PostgresReady -EnvMap $envs
Ensure-ApplicationDatabase -EnvMap $envs
Run-DjangoSetup -EnvMap $envs

foreach ($svc in $Script:Services) {
    Write-SafeHost "Servicio listo: $svc"
}
