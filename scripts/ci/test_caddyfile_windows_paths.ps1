$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$commonScript = Join-Path $repoRoot "deploy\windows-native\scripts\common.ps1"
$templatePath = Join-Path $repoRoot "deploy\windows-native\caddy\Caddyfile.template"

$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($commonScript, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {
    $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber) $($_.Message)" }) -join "; "
    throw "[CADDY_PATH_TEST] common.ps1 parse failed: $details"
}

$functionNames = @(
    "ConvertTo-CaddyPath",
    "ConvertTo-CaddyfileLiteral",
    "Quote-CaddyPath"
)
$functionAsts = $ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $functionNames -contains $node.Name
}, $true)

foreach ($name in $functionNames) {
    $match = $functionAsts | Where-Object { $_.Name -eq $name } | Select-Object -First 1
    if (-not $match) {
        throw "[CADDY_PATH_TEST] Missing function: $name"
    }
    Invoke-Expression $match.Extent.Text
}

if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
    throw "[CADDY_PATH_TEST] Missing Caddyfile.template"
}

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("Pico Caddy Path Test " + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$caddyfile = Join-Path $tempDir "Caddyfile"

try {
    $programFilesDir = "C:\Program Files\PicoDeGallo"
    $programDataDir = "C:\ProgramData\PicoDeGallo"
    $content = (Get-Content -LiteralPath $templatePath -Raw).
        Replace("{{APP_BIND_ADDRESS}}", "127.0.0.1").
        Replace("{{APP_HTTP_PORT}}", "9282").
        Replace("{{BACKEND_HTTP_PORT}}", "8000").
        Replace("{{PROGRAM_DATA_DIR}}/static", (Quote-CaddyPath -Path (Join-Path $programDataDir "static"))).
        Replace("{{PROGRAM_DATA_DIR}}/media", (Quote-CaddyPath -Path (Join-Path $programDataDir "media"))).
        Replace("{{PROGRAM_FILES_DIR}}/frontend", (Quote-CaddyPath -Path (Join-Path $programFilesDir "frontend"))).
        Replace("{{STATIC_ROOT_DIR}}", (Quote-CaddyPath -Path (Join-Path $programDataDir "static"))).
        Replace("{{MEDIA_ROOT_DIR}}", (Quote-CaddyPath -Path (Join-Path $programDataDir "media"))).
        Replace("{{FRONTEND_ROOT_DIR}}", (Quote-CaddyPath -Path (Join-Path $programFilesDir "frontend"))).
        Replace("{{PROGRAM_FILES_DIR}}", (ConvertTo-CaddyPath -Path $programFilesDir)).
        Replace("{{PROGRAM_DATA_DIR}}", (ConvertTo-CaddyPath -Path $programDataDir))

    [System.IO.File]::WriteAllText($caddyfile, $content, (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false)))

    if ($content.Contains("{{")) {
        throw "[CADDY_PATH_TEST] Rendered Caddyfile still contains placeholders"
    }
    if ($content -match 'root\s+\*\s+C:/Program Files') {
        throw "[CADDY_PATH_TEST] Program Files root path is not quoted"
    }
    if ($content -match 'root\s+\*\s+C:\\Program Files') {
        throw "[CADDY_PATH_TEST] Program Files root path uses unquoted backslashes"
    }
    foreach ($expected in @(
        'root * "C:/ProgramData/PicoDeGallo/static"',
        'root * "C:/ProgramData/PicoDeGallo/media"',
        'root * "C:/Program Files/PicoDeGallo/frontend"'
    )) {
        if (-not $content.Contains($expected)) {
            throw "[CADDY_PATH_TEST] Missing expected quoted root: $expected"
        }
    }
    foreach ($line in @($content -split "`r?`n")) {
        if ($line -match '^\s*root\s+\*\s+' -and $line -notmatch '^\s*root\s+\*\s+"[^"]+"\s*$') {
            throw "[CADDY_PATH_TEST] root path is not a single quoted literal: $line"
        }
    }

    $caddyExe = [string]$env:PICOPOS_CADDY_EXE
    $resolvedPath = Join-Path $repoRoot "release\runtime-cache\resolved-runtimes.json"
    if ([string]::IsNullOrWhiteSpace($caddyExe) -and (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        $resolved = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json
        $caddyExe = [string]$resolved.caddy
    }
    if ([string]::IsNullOrWhiteSpace($caddyExe)) {
        $cmd = Get-Command caddy -ErrorAction SilentlyContinue
        if ($cmd) {
            $caddyExe = [string]$cmd.Source
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($caddyExe) -and (Test-Path -LiteralPath $caddyExe -PathType Leaf)) {
        & $caddyExe validate --config $caddyfile
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            throw "[CADDY_PATH_TEST] caddy validate failed with exit code $exitCode"
        }
        Write-Host "Caddyfile Windows path quoting fixture OK with caddy validate."
    } else {
        Write-Host "Caddyfile Windows path quoting fixture OK; caddy validate skipped because caddy.exe is unavailable."
    }
} finally {
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
