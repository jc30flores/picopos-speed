param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    throw $Message
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

function Assert-SafeUrl {
    param(
        [string]$Name,
        [string]$Url
    )

    if ([string]::IsNullOrWhiteSpace($Url)) {
        Fail "URL faltante para ${Name}."
    }

    if (-not ($Url -match '^https://')) {
        Fail "URL no HTTPS para ${Name}."
    }

    if ($Url -match '(?i)\blatest\b|replace-with|example\.com|bit\.ly|tinyurl|goo\.gl') {
        Fail "URL insegura/no versionada para ${Name}."
    }
}

function Assert-Sha256 {
    param(
        [string]$Name,
        [string]$Sha256
    )

    if ([string]::IsNullOrWhiteSpace($Sha256)) {
        Fail "SHA256 faltante para ${Name}."
    }

    if (-not ($Sha256 -match '^[a-fA-F0-9]{64}$')) {
        Fail "SHA256 inválido para ${Name}."
    }
}

function Get-DownloadFileName {
    param(
        [string]$Name,
        [string]$Url
    )

    $uri = [Uri]$Url
    $fileName = [System.IO.Path]::GetFileName($uri.AbsolutePath)

    if ([string]::IsNullOrWhiteSpace($fileName)) {
        Fail "No se pudo resolver nombre de archivo para ${Name}."
    }

    return $fileName
}

function Resolve-PostgresRoot {
    param([string]$ExtractDir)

    $postgresExe = Get-ChildItem -Path $ExtractDir -Recurse -File -Filter "postgres.exe" |
        Where-Object { $_.FullName -match '[\\/]bin[\\/]postgres\.exe$' } |
        Select-Object -First 1

    if (-not $postgresExe) {
        Fail "No se encontró postgres.exe dentro del runtime PostgreSQL."
    }

    $binDir = Split-Path -Parent $postgresExe.FullName
    return (Split-Path -Parent $binDir)
}

function Resolve-CaddyExe {
    param([string]$ExtractDir)

    $caddyExe = Get-ChildItem -Path $ExtractDir -Recurse -File -Filter "caddy.exe" |
        Select-Object -First 1

    if (-not $caddyExe) {
        Fail "No se encontró caddy.exe dentro del runtime Caddy."
    }

    return $caddyExe.FullName
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    Fail "No existe manifest de runtimes: $ManifestPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$downloadsDir = Join-Path $OutputDir "downloads"
$extractDir = Join-Path $OutputDir "extracted"

New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json

# Soporta dos estructuras:
# 1. { "python": {...}, "postgres": {...}, ... }
# 2. { "runtimes": { "python": {...}, ... } }
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

    if ([string]::IsNullOrWhiteSpace([string]$version) -or [string]$version -match 'replace-with|example|latest') {
        Fail "Versión inválida para ${key}."
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
        Fail "SHA256 no coincide para ${key}. Esperado=$expectedHash Actual=$actualHash"
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
                $pythonExe = Get-ChildItem -Path $runtimeExtractDir -Recurse -File -Filter "python.exe" | Select-Object -First 1
                if (-not $pythonExe) {
                    Fail "No se encontró python.exe dentro del runtime Python."
                }
                $resolved[$key] = (Split-Path -Parent $pythonExe.FullName)
            }
            elseif ($key -eq "postgres") {
                $resolved[$key] = Resolve-PostgresRoot -ExtractDir $runtimeExtractDir
            }
            elseif ($key -eq "caddy") {
                $resolved[$key] = Resolve-CaddyExe -ExtractDir $runtimeExtractDir
            }
            else {
                $resolved[$key] = $runtimeExtractDir
            }
        }

        "file" {
            $resolved[$key] = $downloadPath
        }

        "installer" {
            $resolved[$key] = $downloadPath
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

$outFile = Join-Path $OutputDir "resolved-runtimes.json"
$resolved | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outFile -Encoding UTF8

Write-Host "resolved-runtimes.json generado correctamente."
Write-Host "Runtimes resueltos: $($resolved.Keys -join ', ')"
