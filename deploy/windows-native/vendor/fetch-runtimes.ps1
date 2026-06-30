param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot "runtime-manifest.json"),

    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    throw "[RUNTIME_RESOLVE] $Message"
}

function Get-PropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        $Object,

        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    foreach ($name in $Names) {
        if ($Object.PSObject.Properties.Name -contains $name) {
            return $Object.$name
        }
    }

    return $null
}

function Resolve-AbsolutePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Resolve-Path -LiteralPath $Path).Path
}

function Assert-SafeUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url
    )

    if ([string]::IsNullOrWhiteSpace($Url)) {
        Fail "URL faltante para ${Name}."
    }

    $uri = $null
    if (-not [Uri]::TryCreate($Url, [UriKind]::Absolute, [ref]$uri)) {
        Fail "URL invalida para ${Name}."
    }

    if ($uri.Scheme -ne "https") {
        Fail "URL no HTTPS para ${Name}."
    }

    $blockedHosts = @(
        "example.com",
        "www.example.com",
        "example.invalid",
        "bit.ly",
        "tinyurl.com",
        "goo.gl",
        "t.co",
        "ow.ly",
        "is.gd",
        "buff.ly",
        "rebrand.ly",
        "cutt.ly",
        "tiny.cc"
    )
    $runtimeHost = $uri.Host.ToLowerInvariant()
    if ($blockedHosts -contains $runtimeHost) {
        Fail "URL insegura/no versionada para ${Name}."
    }

    if ($Url -match "(?i)(^|[/?=&._-])latest([/?=&._-]|$)|replace-with|example\.") {
        Fail "URL insegura/no versionada para ${Name}."
    }
}

function Assert-Sha256 {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Sha256
    )

    if ([string]::IsNullOrWhiteSpace($Sha256)) {
        Fail "SHA256 faltante para ${Name}."
    }

    if (-not ($Sha256 -match "^[a-fA-F0-9]{64}$")) {
        Fail "SHA256 invalido para ${Name}."
    }
}

function Get-DownloadFileName {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url
    )

    $uri = [Uri]$Url
    $fileName = [System.IO.Path]::GetFileName($uri.AbsolutePath)

    if ([string]::IsNullOrWhiteSpace($fileName)) {
        Fail "No se pudo resolver nombre de archivo para ${Name}."
    }

    return $fileName
}

function Resolve-PostgresRoot {
    param([Parameter(Mandatory = $true)][string]$ExtractDir)

    $postgresExe = Get-ChildItem -LiteralPath $ExtractDir -Recurse -File -Filter "postgres.exe" |
        Where-Object { $_.FullName -match "[\\/]bin[\\/]postgres\.exe$" } |
        Select-Object -First 1

    if (-not $postgresExe) {
        Fail "No se encontro postgres.exe dentro del runtime PostgreSQL."
    }

    $binDir = Split-Path -Parent $postgresExe.FullName
    return (Split-Path -Parent $binDir)
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

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        Fail "PostgreSQL runtime no es una carpeta: $Path"
    }

    foreach ($dir in @("bin", "lib", "share")) {
        if (-not (Test-Path -LiteralPath (Join-Path $Path $dir) -PathType Container)) {
            Fail "PostgreSQL runtime minimo no contiene ${dir}/."
        }
    }

    $requiredTools = @(
        "postgres.exe",
        "pg_ctl.exe",
        "initdb.exe",
        "psql.exe",
        "pg_dump.exe",
        "pg_restore.exe",
        "createdb.exe"
    )

    foreach ($tool in $requiredTools) {
        $candidate = Join-Path (Join-Path $Path "bin") $tool
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            Fail "PostgreSQL runtime minimo no contiene bin\$tool."
        }
    }

    Test-NoForbiddenRuntimeContent -Path $Path
}

function Invoke-PostgresRuntimeVersionChecks {
    param([Parameter(Mandatory = $true)][string]$Path)

    $postgresBin = Join-Path $Path "bin"
    $checks = @(
        @{ Tool = "postgres.exe"; Command = "postgres.exe --version" },
        @{ Tool = "initdb.exe"; Command = "initdb.exe --version" },
        @{ Tool = "psql.exe"; Command = "psql.exe --version" }
    )

    foreach ($check in $checks) {
        $tool = [string]$check.Tool
        $command = [string]$check.Command
        $exe = Join-Path $postgresBin $tool
        $stdout = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-pg-runtime-" + [Guid]::NewGuid().ToString("N") + ".out")
        $stderr = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-pg-runtime-" + [Guid]::NewGuid().ToString("N") + ".err")
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
                $stdoutText = ([string](Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue)).Trim()
            }
            if (Test-Path -LiteralPath $stderr -PathType Leaf) {
                $stderrText = ([string](Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue)).Trim()
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

function Copy-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        Fail "No existe carpeta fuente: $Source"
    }

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Prepare-PostgresRuntime {
    param(
        [Parameter(Mandatory = $true)][string]$ExtractDir,
        [Parameter(Mandatory = $true)][string]$PreparedRoot
    )

    $sourceRoot = Resolve-PostgresRoot -ExtractDir $ExtractDir
    $prepared = Join-Path $PreparedRoot "postgres"

    if (Test-Path -LiteralPath $prepared) {
        Remove-Item -LiteralPath $prepared -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $prepared | Out-Null

    foreach ($dir in @("bin", "lib", "share")) {
        $source = Join-Path $sourceRoot $dir
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            Fail "PostgreSQL fuente no contiene ${dir}/."
        }
        Copy-DirectoryContents -Source $source -Destination (Join-Path $prepared $dir)
    }

    Assert-PostgresRuntime -Path $prepared
    Invoke-PostgresRuntimeVersionChecks -Path $prepared
    return (Resolve-AbsolutePath -Path $prepared)
}

function Resolve-CaddyExe {
    param([Parameter(Mandatory = $true)][string]$ExtractDir)

    $caddyExe = Get-ChildItem -LiteralPath $ExtractDir -Recurse -File -Filter "caddy.exe" |
        Select-Object -First 1

    if (-not $caddyExe) {
        Fail "No se encontro caddy.exe dentro del runtime Caddy."
    }

    return (Resolve-AbsolutePath -Path $caddyExe.FullName)
}

function Assert-ResolvedRuntimes {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Resolved
    )

    $required = @("python", "postgres", "caddy", "winsw", "innoSetup")
    foreach ($key in $required) {
        if (-not $Resolved.Contains($key)) {
            Fail "resolved-runtimes.json no contiene key requerida: $key"
        }

        $value = [string]$Resolved[$key]
        if ([string]::IsNullOrWhiteSpace($value)) {
            Fail "resolved-runtimes.json contiene ruta vacia para $key"
        }
        if (-not [System.IO.Path]::IsPathRooted($value)) {
            Fail "Ruta resuelta no es absoluta para ${key}: $value"
        }
        if (-not (Test-Path -LiteralPath $value)) {
            Fail "Ruta resuelta no existe para ${key}: $value"
        }
    }

    if (-not (Test-Path -LiteralPath (Join-Path ([string]$Resolved["python"]) "python.exe") -PathType Leaf)) {
        Fail "Runtime Python no contiene python.exe."
    }

    Assert-PostgresRuntime -Path ([string]$Resolved["postgres"])
    Invoke-PostgresRuntimeVersionChecks -Path ([string]$Resolved["postgres"])

    $caddy = Get-Item -LiteralPath ([string]$Resolved["caddy"])
    if ($caddy.Name -ne "caddy.exe") {
        Fail "Runtime Caddy debe resolver directamente a caddy.exe."
    }

    foreach ($key in @("winsw", "innoSetup")) {
        $item = Get-Item -LiteralPath ([string]$Resolved[$key])
        if ($item.PSIsContainer -or $item.Extension.ToLowerInvariant() -ne ".exe") {
            Fail "Runtime ${key} debe resolver a un .exe."
        }
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    $manifestJson = $env:WINDOWS_RUNTIME_MANIFEST_JSON
    if ([string]::IsNullOrWhiteSpace($manifestJson)) {
        Fail "No existe manifest de runtimes: $ManifestPath"
    }

    $ManifestPath = Join-Path $OutputDir "runtime-manifest.materialized.json"
    [System.IO.File]::WriteAllText(
        $ManifestPath,
        $manifestJson,
        [System.Text.UTF8Encoding]::new($false)
    )
}

$ManifestPath = Resolve-AbsolutePath -Path $ManifestPath

$downloadsDir = Join-Path $OutputDir "downloads"
$extractDir = Join-Path $OutputDir "extracted"
$preparedDir = Join-Path $OutputDir "prepared"

New-Item -ItemType Directory -Force -Path $downloadsDir, $extractDir, $preparedDir | Out-Null

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json

if ($manifest.PSObject.Properties.Name -contains "runtimes") {
    $runtimeContainer = $manifest.runtimes
} else {
    $runtimeContainer = $manifest
}

$required = @("python", "postgres", "caddy", "winsw", "innoSetup")
$resolved = [ordered]@{}

foreach ($key in $required) {
    if (-not ($runtimeContainer.PSObject.Properties.Name -contains $key)) {
        Fail "Manifest no contiene runtime requerido: $key"
    }

    $item = $runtimeContainer.$key
    $name = Get-PropertyValue -Object $item -Names @("name")
    if ([string]::IsNullOrWhiteSpace([string]$name)) {
        $name = $key
    }

    $version = Get-PropertyValue -Object $item -Names @("version")
    $url = Get-PropertyValue -Object $item -Names @("url")
    $sha256 = Get-PropertyValue -Object $item -Names @("sha256")
    $strategy = Get-PropertyValue -Object $item -Names @("extract_strategy", "archiveType", "archive_type", "strategy")

    if ([string]::IsNullOrWhiteSpace([string]$strategy)) {
        Fail "extract_strategy/archiveType faltante para ${key}."
    }

    $strategy = ([string]$strategy).Trim().ToLowerInvariant()

    if ([string]::IsNullOrWhiteSpace([string]$version) -or [string]$version -match "(?i)replace-with|example|latest") {
        Fail "Version invalida para ${key}."
    }

    Assert-SafeUrl -Name $key -Url ([string]$url)
    Assert-Sha256 -Name $key -Sha256 ([string]$sha256)

    $fileName = Get-DownloadFileName -Name $key -Url ([string]$url)
    $downloadPath = Join-Path $downloadsDir $fileName

    Write-Host "Descargando runtime verificado: $key $version"
    Invoke-WebRequest -Uri ([string]$url) -OutFile $downloadPath -UseBasicParsing

    $actualHash = (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $expectedHash = ([string]$sha256).ToLowerInvariant()

    if ($actualHash -ne $expectedHash) {
        throw "[HASH_MISMATCH] SHA256 no coincide para ${key}. Esperado=$expectedHash Actual=$actualHash"
    }

    Write-Host "SHA256 OK: $key"

    switch ($strategy) {
        "zip" {
            $runtimeExtractDir = Join-Path $extractDir $key
            if (Test-Path -LiteralPath $runtimeExtractDir) {
                Remove-Item -LiteralPath $runtimeExtractDir -Recurse -Force
            }

            New-Item -ItemType Directory -Force -Path $runtimeExtractDir | Out-Null
            Expand-Archive -LiteralPath $downloadPath -DestinationPath $runtimeExtractDir -Force

            if ($key -eq "python") {
                $pythonExe = Get-ChildItem -LiteralPath $runtimeExtractDir -Recurse -File -Filter "python.exe" | Select-Object -First 1
                if (-not $pythonExe) {
                    Fail "No se encontro python.exe dentro del runtime Python."
                }
                $resolved[$key] = Resolve-AbsolutePath -Path (Split-Path -Parent $pythonExe.FullName)
            } elseif ($key -eq "postgres") {
                $resolved[$key] = Prepare-PostgresRuntime -ExtractDir $runtimeExtractDir -PreparedRoot $preparedDir
            } elseif ($key -eq "caddy") {
                $resolved[$key] = Resolve-CaddyExe -ExtractDir $runtimeExtractDir
            } else {
                $resolved[$key] = Resolve-AbsolutePath -Path $runtimeExtractDir
            }
        }

        "file" {
            $resolved[$key] = Resolve-AbsolutePath -Path $downloadPath
        }

        "installer" {
            $resolved[$key] = Resolve-AbsolutePath -Path $downloadPath
        }

        default {
            Fail "extract_strategy/archiveType no soportado para ${key}: $strategy"
        }
    }

    if ([string]::IsNullOrWhiteSpace([string]$resolved[$key]) -or -not (Test-Path -LiteralPath $resolved[$key])) {
        Fail "No se pudo resolver ruta final para ${key}."
    }

    Write-Host "Runtime resuelto: $key"
}

Assert-ResolvedRuntimes -Resolved $resolved

$outFile = Join-Path $OutputDir "resolved-runtimes.json"
$resolved | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outFile -Encoding UTF8

Write-Host "resolved-runtimes.json generado correctamente."
Write-Host "Runtimes resueltos: $($resolved.Keys -join ', ')"
