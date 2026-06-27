param(
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$ReleaseDir,
    [string]$OutputDir = "release/installers",
    [string]$InnoSetupCompilerPath = "ISCC.exe",
    [string]$SignToolPath,
    [string]$CodeSigningCertPath,
    [string]$CodeSigningTimestampUrl = "http://timestamp.digicert.com",
    [switch]$SkipSigning
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Find-RepoRoot {
    $dir = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
    if (-not (Test-Path (Join-Path $dir "deploy\windows-native\installer\PicoDeGallo.iss"))) { throw "No se encontró la raíz del repositorio." }
    return $dir.Path
}
function Fail([string]$Message) { throw "[build-installer] $Message" }
function Test-NoForbiddenReleaseFiles([string]$Root) {
    $bad = Get-ChildItem -LiteralPath $Root -Recurse -Force -File | Where-Object {
        $_.FullName -match '\\backend\\\.env$' -or
        $_.Name -eq '.env.windows' -or
        $_.FullName -match '\\media\\' -or
        $_.FullName -match '\\dumps\\' -or
        $_.FullName -match '\\backups\\' -or
        $_.FullName -match '\\diagnostics\\'
    }
    if ($bad) { Fail "Release contiene archivos no permitidos: $($bad[0].FullName)" }
}
function Test-NoObviousSecrets([string]$Root) {
    $files = Get-ChildItem -LiteralPath $Root -Recurse -Force -File -Include '*.env','*.txt','*.json','*.config','*.xml','*.ps1'
    $hits = $files | Select-String -Pattern 'DTE_API_TOKEN=ey|DJANGO_SECRET_KEY=django-insecure-[A-Za-z0-9_-]{30,}' -ErrorAction SilentlyContinue
    if ($hits) { Fail "Posible secreto en release: $($hits[0].Path)" }
}

$repoRoot = Find-RepoRoot
$release = Resolve-Path -LiteralPath $ReleaseDir
$required = @('ProgramFiles\PicoDeGallo\backend','ProgramFiles\PicoDeGallo\frontend','ProgramFiles\PicoDeGallo\python','ProgramFiles\PicoDeGallo\postgres','ProgramFiles\PicoDeGallo\caddy','ProgramFiles\PicoDeGallo\services','ProgramFiles\PicoDeGallo\scripts','ProgramFiles\PicoDeGallo\version.json','manifest.json')
foreach ($item in $required) { if (-not (Test-Path (Join-Path $release $item))) { Fail "ReleaseDir no contiene $item" } }
Test-NoForbiddenReleaseFiles $release
Test-NoObviousSecrets $release
$out = Join-Path $repoRoot $OutputDir
New-Item -ItemType Directory -Path $out -Force | Out-Null
$issTemplate = Join-Path $repoRoot 'deploy\windows-native\installer\PicoDeGallo.iss'
$issWork = Join-Path $out "PicoDeGallo-$Version.iss"
(Get-Content $issTemplate -Raw) -replace '#define MyAppVersion "0.0.0-dev"', "#define MyAppVersion `"$Version`"" -replace '#define SourceRoot "..\\..\\..\\release\\windows-native"', "#define SourceRoot `"$($release.Path -replace '\\','\\')`"" | Set-Content -Path $issWork -Encoding UTF8
& $InnoSetupCompilerPath $issWork "/O$out"
if ($LASTEXITCODE -ne 0) { Fail "ISCC.exe falló con código $LASTEXITCODE" }
$installer = Get-ChildItem -LiteralPath $out -Filter "PicoDeGallo-Setup-$Version*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) { Fail "No se encontró el instalador generado." }
if (-not $SkipSigning) {
    if ([string]::IsNullOrWhiteSpace($SignToolPath) -or [string]::IsNullOrWhiteSpace($CodeSigningCertPath)) { Fail "Firma habilitada pero falta SignToolPath o CodeSigningCertPath." }
    & $SignToolPath sign /fd SHA256 /f $CodeSigningCertPath /tr $CodeSigningTimestampUrl /td SHA256 $installer.FullName
    if ($LASTEXITCODE -ne 0) { Fail "Firma de código falló." }
}
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $installer.FullName
$hash.Hash | Set-Content -Path ($installer.FullName + '.sha256') -Encoding ASCII
@{ version=$Version; installer=$installer.FullName; sha256=$hash.Hash; release=$release.Path; builtAt=(Get-Date -Format o); signed=(-not $SkipSigning) } | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $out "PicoDeGallo-Setup-$Version.manifest.json") -Encoding UTF8
Write-Host "Instalador generado: $($installer.FullName)"
