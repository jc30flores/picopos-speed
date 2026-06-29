param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$ReleaseDir,
    [string]$OutputDir = "release/installers",
    [Alias("InnoSetupCompilerPath")][string]$ISCCPath = "ISCC.exe",
    [string]$SignToolPath,
    [string]$CodeSigningCertPath,
    [string]$CodeSigningTimestampUrl = "http://timestamp.digicert.com",
    [switch]$SkipSigning
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Find-RepoRoot {
    $dir = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
    if (-not (Test-Path -LiteralPath (Join-Path $dir "deploy\windows-native\installer\PicoDeGallo.iss") -PathType Leaf)) {
        throw "No se encontro la raiz del repositorio."
    }
    return $dir.Path
}

function Fail {
    param([string]$Message)
    throw "[build-installer] $Message"
}

function Test-NoForbiddenReleaseFiles {
    param([Parameter(Mandatory = $true)][string]$Root)

    $nodeModulesName = "node" + "_modules"
    $pgGuiName = "pg" + "Admin"
    $stackBuilderName = "Stack" + "Builder"
    $yarnStateName = ".yarn" + "-state.yml"

    $badDir = Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @($nodeModulesName, $pgGuiName, $stackBuilderName, ".git", ".github") } |
        Select-Object -First 1
    if ($badDir) {
        Fail "Release contiene carpeta no permitida: $($badDir.FullName)"
    }

    $badFile = Get-ChildItem -LiteralPath $Root -Recurse -Force -File -ErrorAction SilentlyContinue |
        Where-Object {
            $relative = $_.FullName.Substring($Root.Length).TrimStart("\", "/")
            $sqlAllowed = $relative -match "(?i)(^|[\\/])ProgramFiles[\\/]PicoDeGallo[\\/]postgres[\\/]share[\\/]"
            $_.Name -in @(".env", ".env.windows", ".env.docker", $yarnStateName) -or
            $relative -match "(?i)(^|[\\/])backend[\\/]\.env$" -or
            $relative -match "(?i)(^|[\\/])ProgramData[\\/]PicoDeGallo[\\/](media|backups|diagnostics|dumps)[\\/]" -or
            $relative -match "[\\/]$([regex]::Escape($nodeModulesName))[\\/]" -or
            $_.Name -match "(?i)\.(dump|pyc|pyo)$" -or
            ($_.Name -match "(?i)\.sql$" -and -not $sqlAllowed) -or
            ($_.Name -eq "package-lock.json" -and $relative -match "(?i)(^|[\\/])ProgramFiles[\\/]PicoDeGallo[\\/](python|postgres|caddy|services)[\\/]")
        } |
        Select-Object -First 1
    if ($badFile) {
        Fail "Release contiene archivo no permitido: $($badFile.FullName)"
    }
}

function Test-NoObviousSecrets {
    param([Parameter(Mandatory = $true)][string]$Root)

    $files = Get-ChildItem -LiteralPath $Root -Recurse -Force -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Length -lt 1048576 -and
            $_.Extension.ToLowerInvariant() -in @(".env", ".example", ".txt", ".json", ".config", ".xml", ".ps1", ".cmd", ".bat", ".ini", ".yml", ".yaml")
        }

    $patterns = @(
        "(?im)^\s*DB_PASSWORD\s*=\s*(?!replace-with|placeholder|example|changeme|\s*$).{8,}$",
        "(?im)^\s*DTE_API_TOKEN\s*=\s*(?!replace-with|placeholder|example|changeme|\s*$).{12,}$",
        "(?im)^\s*DJANGO_SECRET_KEY\s*=\s*(?!replace-with|placeholder|example|changeme|\s*$).{20,}$",
        "(?i)Bearer[ \t]+[A-Za-z0-9._~+/=-]{24,}"
    )

    foreach ($file in $files) {
        $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        foreach ($pattern in $patterns) {
            if ($content -match $pattern) {
                Fail "Posible secreto en release: $($file.FullName)"
            }
        }
    }
}

function Test-RequiredReleaseLayout {
    param([Parameter(Mandatory = $true)][string]$Root)

    $required = @(
        "ProgramFiles\PicoDeGallo\backend",
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
        "ProgramFiles\PicoDeGallo\scripts",
        "ProgramFiles\PicoDeGallo\scripts\open-kiosk.ps1",
        "ProgramFiles\PicoDeGallo\version.json",
        "ProgramData\PicoDeGallo\config\.env.example",
        "manifest.json"
    )

    foreach ($item in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $item))) {
            Fail "ReleaseDir no contiene $item"
        }
    }

    $pythonRoot = Join-Path $Root "ProgramFiles\PicoDeGallo\python"
    $sitePackages = Join-Path $pythonRoot "Lib\site-packages"
    $pthFile = Get-ChildItem -LiteralPath $pythonRoot -Filter "python*._pth" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pthFile) {
        Fail "Runtime Python embebido no contiene python*._pth."
    }
    $pthContent = Get-Content -LiteralPath $pthFile.FullName -Raw
    if ($pthContent -notmatch "(?m)^Lib\\site-packages$" -or $pthContent -notmatch "(?m)^import site$") {
        Fail "Runtime Python embebido no habilita Lib\site-packages e import site."
    }
    foreach ($module in @("django", "waitress", "psycopg2", "requests")) {
        if (-not (Test-Path -LiteralPath (Join-Path $sitePackages $module))) {
            Fail "Runtime Python embebido no contiene modulo requerido: $module"
        }
    }
}

$repoRoot = Find-RepoRoot
$release = Resolve-Path -LiteralPath $ReleaseDir
Test-RequiredReleaseLayout -Root $release.Path
Test-NoForbiddenReleaseFiles -Root $release.Path
Test-NoObviousSecrets -Root $release.Path

if ([string]::IsNullOrWhiteSpace($ISCCPath) -or -not (Test-Path -LiteralPath $ISCCPath -PathType Leaf)) {
    Fail "No existe ISCC.exe: $ISCCPath"
}

$out = Join-Path $repoRoot $OutputDir
New-Item -ItemType Directory -Path $out -Force | Out-Null

$issTemplate = Join-Path $repoRoot "deploy\windows-native\installer\PicoDeGallo.iss"
$issWork = Join-Path $out "PicoDeGallo-$Version.iss"
$issContent = Get-Content -LiteralPath $issTemplate -Raw
$issContent = $issContent.Replace('#define MyAppVersion "0.0.0-dev"', ('#define MyAppVersion "{0}"' -f $Version))
$issContent = $issContent.Replace('#define SourceRoot "..\..\..\release\windows-native"', ('#define SourceRoot "{0}"' -f $release.Path))
$issContent | Set-Content -LiteralPath $issWork -Encoding UTF8

& $ISCCPath $issWork "/O$out"
if ($LASTEXITCODE -ne 0) {
    Fail "ISCC.exe fallo con codigo $LASTEXITCODE"
}

$expectedInstaller = Join-Path $out "PicoDeGallo-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $expectedInstaller -PathType Leaf)) {
    Fail "No se encontro el instalador generado: $expectedInstaller"
}
$installer = Get-Item -LiteralPath $expectedInstaller

if (-not $SkipSigning) {
    if ([string]::IsNullOrWhiteSpace($SignToolPath) -or [string]::IsNullOrWhiteSpace($CodeSigningCertPath)) {
        Fail "Firma habilitada pero falta SignToolPath o CodeSigningCertPath."
    }
    & $SignToolPath sign /fd SHA256 /f $CodeSigningCertPath /tr $CodeSigningTimestampUrl /td SHA256 $installer.FullName
    if ($LASTEXITCODE -ne 0) {
        Fail "Firma de codigo fallo."
    }
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $installer.FullName
$hash.Hash | Set-Content -LiteralPath ($installer.FullName + ".sha256") -Encoding ASCII

$manifest = [ordered]@{
    version = $Version
    installer = $installer.Name
    sha256 = $hash.Hash
    release = $release.Path
    builtAt = (Get-Date -Format o)
    signed = (-not $SkipSigning)
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out "manifest.json") -Encoding UTF8
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out "PicoDeGallo-Setup-$Version.manifest.json") -Encoding UTF8

Write-Host "Instalador generado: $($installer.FullName)"
