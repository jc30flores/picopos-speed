param(
    [Parameter(Mandatory=$true)][string]$Version,
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

function Copy-TreeFiltered([string]$Source, [string]$Destination) {
    robocopy $Source $Destination /E /XD ".git" "venv" "__pycache__" "media" "backups" "dumps" "node_modules" "dist" /XF ".env" ".env.*" "*.pyc" "*.dump" "*.sql" | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "robocopy failed for $Source" }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not (Test-Path (Join-Path $repoRoot "backend\manage.py"))) { throw "Ejecuta package-release.ps1 desde un checkout válido del repositorio." }
$releaseRoot = Join-Path (Resolve-Path $repoRoot).Path $OutputDir
$programFiles = Join-Path $releaseRoot "ProgramFiles\PicoDeGallo"
$programData = Join-Path $releaseRoot "ProgramData\PicoDeGallo"
Remove-Item -LiteralPath $releaseRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $programFiles,$programData | Out-Null

Copy-TreeFiltered (Join-Path $repoRoot "backend") (Join-Path $programFiles "backend")
New-Item -ItemType Directory -Path (Join-Path $programFiles "frontend") -Force | Out-Null
if (-not $SkipFrontendBuild) {
    Push-Location (Join-Path $repoRoot "frontend")
    npm run build
    Pop-Location
    Copy-Item -Path (Join-Path $repoRoot "frontend\dist\*") -Destination (Join-Path $programFiles "frontend") -Recurse -Force
}
Copy-Item -Path (Join-Path $PSScriptRoot "scripts") -Destination (Join-Path $programFiles "scripts") -Recurse -Force
Copy-Item -Path (Join-Path $PSScriptRoot "service-templates") -Destination (Join-Path $programFiles "services") -Recurse -Force
Copy-Item -Path (Join-Path $PSScriptRoot "caddy") -Destination (Join-Path $programFiles "caddy") -Recurse -Force
Copy-Item -Path (Join-Path $PSScriptRoot ".env.windows.example") -Destination (Join-Path $programData "config\.env.example") -Force
Copy-Item -Path (Join-Path $PSScriptRoot ".env.windows.example") -Destination (Join-Path $programFiles ".env.windows.example") -Force
foreach ($dir in @("config","media","static","dte_logs","backups","diagnostics","logs","postgres-data")) { New-Item -ItemType Directory -Path (Join-Path $programData $dir) -Force | Out-Null }

$missing = @()
foreach ($pair in @(@("python",$PythonRuntimePath), @("postgres",$PostgresRuntimePath), @("caddy\caddy.exe",$CaddyPath), @("services\winsw.exe",$WinSWPath))) {
    if ([string]::IsNullOrWhiteSpace($pair[1])) { $missing += $pair[0]; continue }
    if (-not (Test-Path -LiteralPath $pair[1])) { throw "No existe runtime: $($pair[1])" }
    $target = Join-Path $programFiles $pair[0]
    New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $pair[1] -Destination $target -Recurse -Force
}

if (-not $SkipDependencyInstall -and -not [string]::IsNullOrWhiteSpace($PythonRuntimePath)) {
    $pythonExe = Join-Path $programFiles "python\python.exe"
    if (Test-Path $pythonExe) { & $pythonExe -m pip install --no-index --find-links (Join-Path $programFiles "wheels") -r (Join-Path $programFiles "backend\requirements.txt") }
}
$status = if ($missing.Count -eq 0) { "INSTALLABLE" } else { "NOT_INSTALLABLE" }
$versionJson = @{ version=$Version; builtAt=(Get-Date -Format o); status=$status } | ConvertTo-Json -Depth 4
$versionJson | Set-Content -Path (Join-Path $programFiles "version.json") -Encoding UTF8
$manifest = @{ name="Pico de Gallo"; version=$Version; installable=($status -eq "INSTALLABLE"); missingRuntimeArtifacts=$missing; programFilesDir="C:/Program Files/PicoDeGallo"; programDataDir="C:/ProgramData/PicoDeGallo"; generatedAt=(Get-Date -Format o) }
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $releaseRoot "manifest.json") -Encoding UTF8
Write-Host "Release preparado en $releaseRoot ($status)"
