param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$OutputDir = "release/windows-native",
    [string]$PythonRuntimePath,
    [string]$PostgresRuntimePath,
    [string]$CaddyPath,
    [string]$WinSWPath,
    [switch]$SkipFrontendBuild,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Fail {
    param([string]$Message)
    throw "[PACKAGE_RELEASE] $Message"
}

function New-DirectorySafe {
    param([Parameter(Mandatory = $true)][string]$Path)
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Copy-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        Fail "No existe carpeta fuente: $Source"
    }

    New-DirectorySafe $Destination
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Copy-TreeFiltered {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        Fail "No existe carpeta fuente: $Source"
    }

    New-DirectorySafe $Destination
    $nodeModulesName = "node" + "_modules"
    $excludedDirs = @(
        ".git",
        ".github",
        "venv",
        ".venv",
        "__pycache__",
        "media",
        "backups",
        "dumps",
        "diagnostics",
        $nodeModulesName,
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov"
    )
    $excludedFiles = @(
        ".env",
        ".env.*",
        "*.pyc",
        "*.pyo",
        "*.dump",
        "*.sql",
        "*.sqlite",
        "*.sqlite3"
    )
    $args = @($Source, $Destination, "/E", "/XD") + $excludedDirs + @("/XF") + $excludedFiles
    & robocopy @args | Out-Null
    if ($LASTEXITCODE -gt 7) {
        Fail "robocopy fallo para $Source"
    }
}

function Assert-RequiredPath {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Path,
        [ValidateSet("Leaf", "Container")][string]$PathType
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        Fail "Falta runtime requerido: $Name"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType $PathType)) {
        Fail "No existe runtime requerido para ${Name}: $Path"
    }
}

function Test-NoForbiddenRuntimeContent {
    param([Parameter(Mandatory = $true)][string]$Path)

    $nodeModulesName = "node" + "_modules"
    $pgGuiName = "pg" + "Admin"
    $stackBuilderName = "Stack" + "Builder"
    $yarnStateName = ".yarn" + "-state.yml"

    $badDir = Get-ChildItem -LiteralPath $Path -Recurse -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @($nodeModulesName, $pgGuiName, $stackBuilderName) } |
        Select-Object -First 1
    if ($badDir) {
        Fail "Runtime contiene carpeta prohibida: $($badDir.FullName)"
    }

    $badFile = Get-ChildItem -LiteralPath $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $yarnStateName -or $_.FullName -match "[\\/]$([regex]::Escape($nodeModulesName))[\\/]" } |
        Select-Object -First 1
    if ($badFile) {
        Fail "Runtime contiene archivo prohibido: $($badFile.FullName)"
    }
}

function Assert-PostgresRuntime {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-RequiredPath -Name "postgres" -Path $Path -PathType Container
    foreach ($dir in @("bin", "lib", "share")) {
        if (-not (Test-Path -LiteralPath (Join-Path $Path $dir) -PathType Container)) {
            Fail "PostgreSQL runtime minimo no contiene ${dir}/."
        }
    }

    foreach ($tool in @("postgres.exe", "pg_ctl.exe", "initdb.exe", "psql.exe", "pg_dump.exe", "pg_restore.exe", "createdb.exe")) {
        if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $Path "bin") $tool) -PathType Leaf)) {
            Fail "PostgreSQL runtime minimo no contiene bin\$tool."
        }
    }

    Test-NoForbiddenRuntimeContent -Path $Path
}

function Invoke-PostgresRuntimeVersionChecks {
    param([Parameter(Mandatory = $true)][string]$Path)

    $postgresRoot = (Resolve-Path -LiteralPath $Path).Path
    $postgresBin = Join-Path $postgresRoot "bin"
    $checks = @(
        @{ Tool = "postgres.exe"; Command = "postgres.exe --version" },
        @{ Tool = "initdb.exe"; Command = "initdb.exe --version" },
        @{ Tool = "psql.exe"; Command = "psql.exe --version" }
    )

    foreach ($check in $checks) {
        $tool = [string]$check.Tool
        $command = [string]$check.Command
        $exe = Join-Path $postgresBin $tool
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            Fail "PostgreSQL runtime no contiene bin\$tool."
        }
        $exe = (Resolve-Path -LiteralPath $exe).Path

        $stdout = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-pg-version-" + [Guid]::NewGuid().ToString("N") + ".out")
        $stderr = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-pg-version-" + [Guid]::NewGuid().ToString("N") + ".err")
        $exitCode = 0
        try {
            Push-Location $postgresBin
            try {
                & $exe --version > $stdout 2> $stderr
                $exitCode = $LASTEXITCODE
            } finally {
                Pop-Location
            }

            $stdoutText = ""
            $stderrText = ""
            if (Test-Path -LiteralPath $stdout -PathType Leaf) {
                $stdoutRaw = Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue
                if ($null -ne $stdoutRaw) {
                    $stdoutText = ([string]$stdoutRaw).Trim()
                }
            }
            if (Test-Path -LiteralPath $stderr -PathType Leaf) {
                $stderrRaw = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
                if ($null -ne $stderrRaw) {
                    $stderrText = ([string]$stderrRaw).Trim()
                }
            }

            if ($exitCode -ne 0) {
                Fail "PostgreSQL runtime fallo al ejecutar $command. ExitCode=$exitCode Stdout=$stdoutText Stderr=$stderrText"
            }
            Write-Host "PostgreSQL runtime OK: $command -> $stdoutText"
        } finally {
            Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-BackendRuntimeImportCheck {
    param([Parameter(Mandatory = $true)][string]$Root)

    $pythonExe = Join-Path $Root "ProgramFiles\PicoDeGallo\python\python.exe"
    $backend = Join-Path $Root "ProgramFiles\PicoDeGallo\backend"
    Assert-RequiredPath -Name "backend manage.py" -Path (Join-Path $backend "manage.py") -PathType Leaf
    foreach ($relative in @(
        "config\__init__.py",
        "config\settings.py",
        "config\wsgi.py",
        "config\asgi.py",
        "apps\core\management\commands\check_runtime_config.py",
        "apps\users\management\commands\bootstrap_initial_admin.py",
        "apps\dte\management\commands\dte_outbox_worker.py",
        "apps\dte\management\commands\dte_monitor.py"
    )) {
        Assert-RequiredPath -Name "backend $relative" -Path (Join-Path $backend $relative) -PathType Leaf
    }

    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-backend-runtime-" + [Guid]::NewGuid().ToString("N"))
    New-DirectorySafe $tempDir
    $envFile = Join-Path $tempDir ".env"
    $envLines = @(
        "DJANGO_CONFIG_MODE=strict",
        "DOTENV_OVERRIDE=false",
        "DJANGO_DEBUG=false",
        "DJANGO_SECRET_KEY=placeholder-django-secret-key-for-packaging-validation",
        "DB_HOST=127.0.0.1",
        "DB_PORT=5432",
        "DB_NAME=picopos",
        "DB_USER=picopos",
        "DB_PASSWORD=placeholder-db-password",
        "ALLOWED_HOSTS=localhost,127.0.0.1",
        "CORS_ALLOWED_ORIGINS=http://127.0.0.1:9282",
        "CSRF_TRUSTED_ORIGINS=http://127.0.0.1:9282",
        ("DJANGO_MEDIA_ROOT={0}" -f (Join-Path $tempDir "media").Replace("\", "/")),
        ("DJANGO_STATIC_ROOT={0}" -f (Join-Path $tempDir "static").Replace("\", "/")),
        ("DTE_LOG_DIR={0}" -f (Join-Path $tempDir "dte_logs").Replace("\", "/")),
        "DTE_BACKGROUND_MODE=external",
        "DTE_BASE_URL=replace-with-dte-api-base-url",
        "DTE_API_TOKEN=replace-with-dte-api-token",
        "DTE_API_AUTH_HEADER=Authorization",
        "DTE_API_AUTH_PREFIX=Bearer",
        "DTE_MONITOR_ENABLED=true",
        "DTE_OUTBOX_WORKER_ENABLED=true"
    )
    [System.IO.File]::WriteAllLines($envFile, $envLines, [System.Text.UTF8Encoding]::new($false))

    $envNames = @("DJANGO_ENV_FILE", "DOTENV_OVERRIDE", "DJANGO_SETTINGS_MODULE", "PYTHONUNBUFFERED")
    $oldEnv = @{}
    foreach ($name in $envNames) {
        $oldEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    }

    try {
        [Environment]::SetEnvironmentVariable("DJANGO_ENV_FILE", $envFile, "Process")
        [Environment]::SetEnvironmentVariable("DOTENV_OVERRIDE", "false", "Process")
        [Environment]::SetEnvironmentVariable("DJANGO_SETTINGS_MODULE", "config.settings", "Process")
        [Environment]::SetEnvironmentVariable("PYTHONUNBUFFERED", "1", "Process")

        Push-Location $backend
        try {
            & $pythonExe -c "import importlib, os; module=os.environ.get('DJANGO_SETTINGS_MODULE') or 'config.settings'; print('DJANGO_SETTINGS_MODULE=' + module); importlib.import_module(module); importlib.import_module('config.wsgi'); print('DJANGO_SETTINGS_IMPORT_OK')"
            if ($LASTEXITCODE -ne 0) {
                Fail "Backend empaquetado no puede importar config.settings/config.wsgi."
            }
            & $pythonExe manage.py help check_runtime_config | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Fail "Backend empaquetado no expone management command check_runtime_config."
            }
        } finally {
            Pop-Location
        }
    } finally {
        foreach ($name in $envNames) {
            [Environment]::SetEnvironmentVariable($name, $oldEnv[$name], "Process")
        }
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "Backend runtime import OK."
}

function Assert-PythonRuntime {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-RequiredPath -Name "python" -Path $Path -PathType Container
    if (-not (Test-Path -LiteralPath (Join-Path $Path "python.exe") -PathType Leaf)) {
        Fail "Runtime Python no contiene python.exe."
    }
}

function Remove-PythonBytecode {
    param([Parameter(Mandatory = $true)][string]$Root)

    Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $Root -Recurse -Force -File -Include "*.pyc", "*.pyo" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Enable-EmbeddedPythonSitePackages {
    param([Parameter(Mandatory = $true)][string]$PythonRoot)

    $sitePackages = Join-Path $PythonRoot "Lib\site-packages"
    New-DirectorySafe $sitePackages

    $pthFile = Get-ChildItem -LiteralPath $PythonRoot -Filter "python*._pth" -File | Select-Object -First 1
    if (-not $pthFile) {
        Fail "Python embeddable no contiene python*._pth."
    }

    $rawLines = @(Get-Content -LiteralPath $pthFile.FullName)
    $cleanLines = @()

    foreach ($line in $rawLines) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "Lib\site-packages") { continue }
        if ($trimmed -eq "import site") { continue }
        if ($trimmed -eq "#import site") { continue }
        $cleanLines += $line
    }

    $cleanLines += "Lib\site-packages"
    $cleanLines += "import site"
    Set-Content -LiteralPath $pthFile.FullName -Value $cleanLines -Encoding ASCII
}

function Install-EmbeddedPythonDependencies {
    param(
        [Parameter(Mandatory = $true)][string]$PythonRoot,
        [Parameter(Mandatory = $true)][string]$Requirements
    )

    $pythonExe = Join-Path $PythonRoot "python.exe"
    $sitePackages = Join-Path $PythonRoot "Lib\site-packages"

    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        Fail "No existe python.exe en runtime embebido."
    }
    if (-not (Test-Path -LiteralPath $Requirements -PathType Leaf)) {
        Fail "No existe requirements.txt para instalar dependencias."
    }

    Enable-EmbeddedPythonSitePackages -PythonRoot $PythonRoot

    $pipCommand = Get-Command pip.exe -ErrorAction SilentlyContinue
    if (-not $pipCommand) {
        $pipCommand = Get-Command pip -ErrorAction SilentlyContinue
    }
    if (-not $pipCommand -or [string]::IsNullOrWhiteSpace($pipCommand.Source)) {
        Fail "No se encontro pip del Python de build para instalar dependencias en el runtime embebido."
    }

    $pipExe = (Resolve-Path -LiteralPath $pipCommand.Source).Path
    $pythonRootResolved = (Resolve-Path -LiteralPath $PythonRoot).Path
    if ($pipExe.StartsWith($pythonRootResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail "pip resuelto pertenece al runtime embebido. Debe usarse pip del Python de build."
    }

    $oldNoBytecode = $env:PYTHONDONTWRITEBYTECODE
    $oldPipNoCache = $env:PIP_NO_CACHE_DIR
    $oldPipDisableVersion = $env:PIP_DISABLE_PIP_VERSION_CHECK

    try {
        $env:PYTHONDONTWRITEBYTECODE = "1"
        $env:PIP_NO_CACHE_DIR = "1"
        $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

        & $pipExe --version
        if ($LASTEXITCODE -ne 0) {
            Fail "pip del Python de build no esta operativo."
        }

        & $pipExe install --disable-pip-version-check --no-cache-dir --no-compile --target $sitePackages -r $Requirements
        if ($LASTEXITCODE -ne 0) {
            Fail "Fallo instalacion de dependencias Python en runtime embebido."
        }

        $pthFile = Get-ChildItem -LiteralPath $PythonRoot -Filter "python*._pth" -File | Select-Object -First 1
        $pthLines = @(Get-Content -LiteralPath $pthFile.FullName | ForEach-Object { ([string]$_).Trim() })
        if (($pthLines -notcontains "Lib\site-packages") -or ($pthLines -notcontains "import site")) {
            Fail "python*._pth no habilita Lib\site-packages e import site."
        }

        & $pythonExe -c "import django, waitress, psycopg2, requests; print('Python runtime OK')"
        if ($LASTEXITCODE -ne 0) {
            Fail "El runtime Python embebido no puede importar django, waitress, psycopg2 y requests."
        }
    } finally {
        $env:PYTHONDONTWRITEBYTECODE = $oldNoBytecode
        $env:PIP_NO_CACHE_DIR = $oldPipNoCache
        $env:PIP_DISABLE_PIP_VERSION_CHECK = $oldPipDisableVersion
    }

    Remove-PythonBytecode -Root $PythonRoot
}

function Test-ReleasePayloadSafety {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        Fail "No existe release root: $Root"
    }

    $nodeModulesName = "node" + "_modules"
    $pgGuiName = "pg" + "Admin"
    $stackBuilderName = "Stack" + "Builder"
    $yarnStateName = ".yarn" + "-state.yml"
    $requiredPaths = @(
        "ProgramFiles\PicoDeGallo\backend\manage.py",
        "ProgramFiles\PicoDeGallo\backend\config\__init__.py",
        "ProgramFiles\PicoDeGallo\backend\config\settings.py",
        "ProgramFiles\PicoDeGallo\backend\config\wsgi.py",
        "ProgramFiles\PicoDeGallo\backend\config\asgi.py",
        "ProgramFiles\PicoDeGallo\backend\apps\core\management\commands\check_runtime_config.py",
        "ProgramFiles\PicoDeGallo\backend\apps\users\management\commands\bootstrap_initial_admin.py",
        "ProgramFiles\PicoDeGallo\backend\apps\dte\management\commands\dte_outbox_worker.py",
        "ProgramFiles\PicoDeGallo\backend\apps\dte\management\commands\dte_monitor.py",
        "ProgramFiles\PicoDeGallo\frontend",
        "ProgramFiles\PicoDeGallo\python\python.exe",
        "ProgramFiles\PicoDeGallo\python\Lib\site-packages",
        "ProgramFiles\PicoDeGallo\postgres\bin\postgres.exe",
        "ProgramFiles\PicoDeGallo\postgres\bin\pg_ctl.exe",
        "ProgramFiles\PicoDeGallo\postgres\bin\initdb.exe",
        "ProgramFiles\PicoDeGallo\postgres\bin\psql.exe",
        "ProgramFiles\PicoDeGallo\postgres\bin\pg_dump.exe",
        "ProgramFiles\PicoDeGallo\postgres\bin\pg_restore.exe",
        "ProgramFiles\PicoDeGallo\postgres\bin\createdb.exe",
        "ProgramFiles\PicoDeGallo\caddy\caddy.exe",
        "ProgramFiles\PicoDeGallo\services\winsw.exe",
        "ProgramFiles\PicoDeGallo\scripts\open-kiosk.ps1",
        "ProgramData\PicoDeGallo\config\.env.example",
        "manifest.json"
    )

    foreach ($path in $requiredPaths) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $path))) {
            Fail "Release incompleto: falta $path"
        }
    }

    $pythonRoot = Join-Path $Root "ProgramFiles\PicoDeGallo\python"
    $sitePackages = Join-Path $pythonRoot "Lib\site-packages"
    $pthFile = Get-ChildItem -LiteralPath $pythonRoot -Filter "python*._pth" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pthFile) {
        Fail "Runtime Python embebido no contiene python*._pth."
    }
    $pthLines = @(Get-Content -LiteralPath $pthFile.FullName | ForEach-Object { ([string]$_).Trim() })
    if (($pthLines -notcontains "Lib\site-packages") -or ($pthLines -notcontains "import site")) {
        Fail "Runtime Python embebido no habilita Lib\site-packages e import site."
    }
    foreach ($module in @("django", "waitress", "psycopg2", "requests")) {
        if (-not (Test-Path -LiteralPath (Join-Path $sitePackages $module))) {
            Fail "Runtime Python embebido no contiene modulo requerido: $module"
        }
    }

    $badDir = Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in @($nodeModulesName, $pgGuiName, $stackBuilderName, ".git", ".github")
        } |
        Select-Object -First 1
    if ($badDir) {
        Fail "Release contiene carpeta prohibida: $($badDir.FullName)"
    }

    $files = @(Get-ChildItem -LiteralPath $Root -Recurse -Force -File)
    $forbiddenFile = $files | Where-Object {
        $relative = $_.FullName.Substring($Root.Length).TrimStart("\", "/")
        $leaf = $_.Name
        $sqlAllowed = $relative -match "(?i)(^|[\\/])ProgramFiles[\\/]PicoDeGallo[\\/]postgres[\\/]share[\\/]"
        $relative -match "(?i)(^|[\\/])backend[\\/]\.env$" -or
        $leaf -in @(".env", ".env.windows", ".env.docker", $yarnStateName) -or
        $relative -match "(?i)(^|[\\/])ProgramData[\\/]PicoDeGallo[\\/](media|backups|diagnostics|dumps)[\\/]" -or
        $relative -match "(?i)(^|[\\/])dumps[\\/]" -or
        $relative -match "[\\/]$([regex]::Escape($nodeModulesName))[\\/]" -or
        $leaf -match "(?i)\.(dump|pyc|pyo)$" -or
        ($leaf -match "(?i)\.sql$" -and -not $sqlAllowed) -or
        ($leaf -eq "package-lock.json" -and $relative -match "(?i)(^|[\\/])ProgramFiles[\\/]PicoDeGallo[\\/](python|postgres|caddy|services)[\\/]")
    } | Select-Object -First 1

    if ($forbiddenFile) {
        Fail "Release contiene archivo prohibido: $($forbiddenFile.FullName)"
    }

    $textFiles = $files | Where-Object {
        $_.Length -lt 1048576 -and $_.Extension.ToLowerInvariant() -in @(".env", ".example", ".json", ".txt", ".config", ".xml", ".ps1", ".cmd", ".bat", ".ini", ".yml", ".yaml")
    }

    $secretPatterns = @(
        @{ Name = "DB_PASSWORD real"; Regex = "(?im)^\s*DB_PASSWORD\s*=\s*(?!replace-with|placeholder|example|changeme|\s*$).{8,}$" },
        @{ Name = "DTE_API_TOKEN real"; Regex = "(?im)^\s*DTE_API_TOKEN\s*=\s*(?!replace-with|placeholder|example|changeme|\s*$).{12,}$" },
        @{ Name = "DJANGO_SECRET_KEY real"; Regex = "(?im)^\s*DJANGO_SECRET_KEY\s*=\s*(?!replace-with|placeholder|example|changeme|\s*$).{20,}$" },
        @{ Name = "Bearer token"; Regex = "(?i)Bearer[ \t]+[A-Za-z0-9._~+/=-]{24,}" }
    )

    foreach ($file in $textFiles) {
        $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        foreach ($pattern in $secretPatterns) {
            if ($content -match $pattern.Regex) {
                Fail "Posible secreto en release ($($pattern.Name)): $($file.FullName)"
            }
        }
    }

    Assert-PostgresRuntime -Path (Join-Path $Root "ProgramFiles\PicoDeGallo\postgres")
    Invoke-PostgresRuntimeVersionChecks -Path (Join-Path $Root "ProgramFiles\PicoDeGallo\postgres")
    Invoke-BackendRuntimeImportCheck -Root $Root
    Write-Host "Release payload safety OK."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "backend\manage.py") -PathType Leaf)) {
    Fail "Ejecuta package-release.ps1 desde un checkout valido del repositorio."
}

Assert-PythonRuntime -Path $PythonRuntimePath
Assert-PostgresRuntime -Path $PostgresRuntimePath
Invoke-PostgresRuntimeVersionChecks -Path $PostgresRuntimePath
Assert-RequiredPath -Name "caddy" -Path $CaddyPath -PathType Leaf
Assert-RequiredPath -Name "winsw" -Path $WinSWPath -PathType Leaf

if ((Get-Item -LiteralPath $CaddyPath).Name -ne "caddy.exe") {
    Fail "CaddyPath debe apuntar directamente a caddy.exe."
}
if ((Get-Item -LiteralPath $WinSWPath).Extension.ToLowerInvariant() -ne ".exe") {
    Fail "WinSWPath debe apuntar a un .exe."
}

$releaseRoot = Join-Path (Resolve-Path $repoRoot).Path $OutputDir
$programFiles = Join-Path $releaseRoot "ProgramFiles\PicoDeGallo"
$programData = Join-Path $releaseRoot "ProgramData\PicoDeGallo"

Remove-Item -LiteralPath $releaseRoot -Recurse -Force -ErrorAction SilentlyContinue

$programFilesDirs = @(
    $programFiles,
    (Join-Path $programFiles "backend"),
    (Join-Path $programFiles "frontend"),
    (Join-Path $programFiles "scripts"),
    (Join-Path $programFiles "services"),
    (Join-Path $programFiles "services\templates"),
    (Join-Path $programFiles "caddy"),
    (Join-Path $programFiles "python"),
    (Join-Path $programFiles "postgres")
)
$programDataDirs = @(
    $programData,
    (Join-Path $programData "config"),
    (Join-Path $programData "media"),
    (Join-Path $programData "static"),
    (Join-Path $programData "dte_logs"),
    (Join-Path $programData "logs"),
    (Join-Path $programData "backups"),
    (Join-Path $programData "diagnostics"),
    (Join-Path $programData "postgres\data")
)

foreach ($dir in ($programFilesDirs + $programDataDirs)) {
    New-DirectorySafe $dir
}

Copy-TreeFiltered -Source (Join-Path $repoRoot "backend") -Destination (Join-Path $programFiles "backend")

if (-not $SkipFrontendBuild) {
    Push-Location (Join-Path $repoRoot "frontend")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) {
            Fail "npm run build fallo."
        }
    } finally {
        Pop-Location
    }
}

$frontendDist = Join-Path $repoRoot "frontend\dist"
if (-not (Test-Path -LiteralPath $frontendDist -PathType Container)) {
    Fail "No existe frontend\dist; ejecute build o revise el paso frontend."
}
Copy-DirectoryContents -Source $frontendDist -Destination (Join-Path $programFiles "frontend")

Copy-DirectoryContents -Source (Join-Path $PSScriptRoot "scripts") -Destination (Join-Path $programFiles "scripts")
Copy-DirectoryContents -Source (Join-Path $PSScriptRoot "service-templates") -Destination (Join-Path $programFiles "services\templates")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "caddy\Caddyfile.template") -Destination (Join-Path $programFiles "caddy\Caddyfile.template") -Force

$thirdParty = Join-Path $PSScriptRoot "installer\THIRD_PARTY_NOTICES.md"
if (-not (Test-Path -LiteralPath $thirdParty -PathType Leaf)) {
    $thirdParty = Join-Path $PSScriptRoot "installer\THIRD_PARTY_NOTICES.template.md"
}
if (Test-Path -LiteralPath $thirdParty -PathType Leaf) {
    Copy-Item -LiteralPath $thirdParty -Destination (Join-Path $programFiles "THIRD_PARTY_NOTICES.md") -Force
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.windows.example") -Destination (Join-Path $programData "config\.env.example") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.windows.example") -Destination (Join-Path $programFiles ".env.windows.example") -Force

Copy-DirectoryContents -Source $PythonRuntimePath -Destination (Join-Path $programFiles "python")
Copy-DirectoryContents -Source $PostgresRuntimePath -Destination (Join-Path $programFiles "postgres")
Copy-Item -LiteralPath $CaddyPath -Destination (Join-Path $programFiles "caddy\caddy.exe") -Force
Copy-Item -LiteralPath $WinSWPath -Destination (Join-Path $programFiles "services\winsw.exe") -Force

if (-not $SkipDependencyInstall) {
    Install-EmbeddedPythonDependencies `
        -PythonRoot (Join-Path $programFiles "python") `
        -Requirements (Join-Path $programFiles "backend\requirements.txt")
}

$versionJson = [ordered]@{
    version = $Version
    builtAt = (Get-Date -Format o)
    status = "INSTALLABLE"
} | ConvertTo-Json -Depth 4
$versionJson | Set-Content -LiteralPath (Join-Path $programFiles "version.json") -Encoding UTF8

$manifest = [ordered]@{
    name = "Pico de Gallo"
    version = $Version
    installable = $true
    programFilesDir = "C:/Program Files/PicoDeGallo"
    programDataDir = "C:/ProgramData/PicoDeGallo"
    generatedAt = (Get-Date -Format o)
    services = @(
        "PicoDeGallo-PostgreSQL",
        "PicoDeGallo-Backend",
        "PicoDeGallo-DTE-Worker",
        "PicoDeGallo-DTE-Monitor",
        "PicoDeGallo-Caddy"
    )
    dte = [ordered]@{
        enabled = $true
        backgroundMode = "external"
        workerService = "PicoDeGallo-DTE-Worker"
        monitorService = "PicoDeGallo-DTE-Monitor"
        contactsHaciendaDuringBuild = $false
    }
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $releaseRoot "manifest.json") -Encoding UTF8

Test-ReleasePayloadSafety -Root $releaseRoot
Write-Host "Release preparado en $releaseRoot (INSTALLABLE)"
