$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$commonScript = Join-Path $repoRoot "deploy\windows-native\scripts\common.ps1"
$templatePath = Join-Path $repoRoot "deploy\windows-native\caddy\Caddyfile.template"

$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($commonScript, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {
    $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber) $($_.Message)" }) -join "; "
    throw "[CADDY_HTTP_TEST] common.ps1 parse failed: $details"
}

$functionNames = @(
    "ConvertTo-WindowsCommandLineArgument",
    "Join-WindowsCommandLineArguments",
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
        throw "[CADDY_HTTP_TEST] Missing function: $name"
    }
    Invoke-Expression $match.Extent.Text
}

if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
    throw "[CADDY_HTTP_TEST] Missing Caddyfile.template"
}

function New-FreeLoopbackPort {
    $ip = [System.Net.IPAddress]::Parse("127.0.0.1")
    $listener = New-Object System.Net.Sockets.TcpListener -ArgumentList @($ip, 0)
    try {
        $listener.Start()
        return [int]$listener.LocalEndpoint.Port
    } finally {
        $listener.Stop()
    }
}

function Resolve-CaddyExe {
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
        return $caddyExe
    }
    return ""
}

function Render-CaddyFixture {
    param(
        [Parameter(Mandatory = $true)][string]$ProgramFilesDir,
        [Parameter(Mandatory = $true)][string]$ProgramDataDir,
        [Parameter(Mandatory = $true)][string]$Port
    )

    return (Get-Content -LiteralPath $templatePath -Raw).
        Replace("{{APP_BIND_ADDRESS}}", "127.0.0.1").
        Replace("{{APP_HTTP_PORT}}", $Port).
        Replace("{{BACKEND_HTTP_PORT}}", "18000").
        Replace("{{PROGRAM_DATA_DIR}}/static", (Quote-CaddyPath -Path (Join-Path $ProgramDataDir "static"))).
        Replace("{{PROGRAM_DATA_DIR}}/media", (Quote-CaddyPath -Path (Join-Path $ProgramDataDir "media"))).
        Replace("{{PROGRAM_FILES_DIR}}/frontend", (Quote-CaddyPath -Path (Join-Path $ProgramFilesDir "frontend"))).
        Replace("{{STATIC_ROOT_DIR}}", (Quote-CaddyPath -Path (Join-Path $ProgramDataDir "static"))).
        Replace("{{MEDIA_ROOT_DIR}}", (Quote-CaddyPath -Path (Join-Path $ProgramDataDir "media"))).
        Replace("{{FRONTEND_ROOT_DIR}}", (Quote-CaddyPath -Path (Join-Path $ProgramFilesDir "frontend"))).
        Replace("{{PROGRAM_FILES_DIR}}", (ConvertTo-CaddyPath -Path $ProgramFilesDir)).
        Replace("{{PROGRAM_DATA_DIR}}", (ConvertTo-CaddyPath -Path $ProgramDataDir))
}

function Assert-CaddyfileLocalHttpContract {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$Port,
        [switch]$ExpectProgramFilesRoot
    )

    if ($Content.Contains("{{")) {
        throw "[CADDY_HTTP_TEST] Rendered Caddyfile still contains placeholders"
    }
    if ($Content -notmatch '(?m)^\s*auto_https\s+off\s*$') {
        throw "[CADDY_HTTP_TEST] Caddyfile must contain auto_https off"
    }
    if ($Content -notmatch ("(?m)^\s*http://127\.0\.0\.1:{0}\s*\{{" -f [regex]::Escape($Port))) {
        throw "[CADDY_HTTP_TEST] Caddyfile must use explicit HTTP loopback site address"
    }
    if ($Content -notmatch '(?m)^\s*bind\s+127\.0\.0\.1\s*$') {
        throw "[CADDY_HTTP_TEST] Caddyfile must contain bind 127.0.0.1"
    }
    if ($Content -match '(?m)^\s*127\.0\.0\.1:\d+\s*\{') {
        throw "[CADDY_HTTP_TEST] Caddyfile contains bare loopback site address without http://"
    }
    if ($Content -match 'root\s+\*\s+C:/Program Files') {
        throw "[CADDY_HTTP_TEST] Program Files root path is not quoted"
    }
    if ($Content -match 'root\s+\*\s+C:\\Program Files') {
        throw "[CADDY_HTTP_TEST] Program Files root path uses unquoted backslashes"
    }
    if ($ExpectProgramFilesRoot -and -not $Content.Contains('root * "C:/Program Files/PicoDeGallo/frontend"')) {
        throw "[CADDY_HTTP_TEST] Missing quoted Program Files frontend root"
    }
}

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("Pico Caddy HTTP Test " + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$process = $null

try {
    $staticContent = Render-CaddyFixture `
        -ProgramFilesDir "C:\Program Files\PicoDeGallo" `
        -ProgramDataDir "C:\ProgramData\PicoDeGallo" `
        -Port "9282"
    Assert-CaddyfileLocalHttpContract -Content $staticContent -Port "9282" -ExpectProgramFilesRoot

    $port = New-FreeLoopbackPort
    $programFilesDir = Join-Path $tempDir "Program Files Pico"
    $programDataDir = Join-Path $tempDir "ProgramData Pico"
    foreach ($dir in @(
        (Join-Path $programFilesDir "frontend"),
        (Join-Path $programDataDir "static"),
        (Join-Path $programDataDir "media")
    )) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    [System.IO.File]::WriteAllText((Join-Path (Join-Path $programFilesDir "frontend") "index.html"), "<!doctype html><title>Pico HTTP OK</title><body>PICO_CADDY_HTTP_OK</body>", (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false)))

    $caddyfile = Join-Path $tempDir "Caddyfile"
    $content = Render-CaddyFixture -ProgramFilesDir $programFilesDir -ProgramDataDir $programDataDir -Port ([string]$port)
    Assert-CaddyfileLocalHttpContract -Content $content -Port ([string]$port)
    [System.IO.File]::WriteAllText($caddyfile, $content, (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false)))

    $caddyExe = Resolve-CaddyExe
    if ([string]::IsNullOrWhiteSpace($caddyExe)) {
        Write-Host "Caddyfile local HTTP fixture OK; caddy validate/run skipped because caddy.exe is unavailable."
        return
    }

    & $caddyExe validate --config $caddyfile
    if ($LASTEXITCODE -ne 0) {
        throw "[CADDY_HTTP_TEST] caddy validate failed with exit code $LASTEXITCODE"
    }

    $stdout = Join-Path $tempDir "caddy.out.log"
    $stderr = Join-Path $tempDir "caddy.err.log"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $caddyExe
    $psi.Arguments = Join-WindowsCommandLineArguments -ArgumentList @("run", "--config", $caddyfile)
    $psi.WorkingDirectory = $tempDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    [void]$process.Start()

    $deadline = (Get-Date).AddSeconds(20)
    $responseText = ""
    do {
        try {
            $response = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/" -f $port) -UseBasicParsing -TimeoutSec 3
            if ([int]$response.StatusCode -eq 200) {
                $responseText = [string]$response.Content
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)

    if ($responseText -notmatch "PICO_CADDY_HTTP_OK") {
        throw "[CADDY_HTTP_TEST] Caddy did not serve frontend over local HTTP"
    }

    if (-not $process.HasExited) {
        $process.Kill()
        $process.WaitForExit()
    }
    [System.IO.File]::WriteAllText($stdout, [string]$process.StandardOutput.ReadToEnd(), (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false)))
    [System.IO.File]::WriteAllText($stderr, [string]$process.StandardError.ReadToEnd(), (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false)))
    $logs = ""
    if (Test-Path -LiteralPath $stdout -PathType Leaf) { $logs += Get-Content -LiteralPath $stdout -Raw }
    if (Test-Path -LiteralPath $stderr -PathType Leaf) { $logs += Get-Content -LiteralPath $stderr -Raw }
    foreach ($bad in @(
        "automatic TLS certificate management",
        "installing root certificate",
        "failed to install root certificate",
        "automatic HTTP->HTTPS redirects",
        "certificate obtained successfully"
    )) {
        if ($logs -match [regex]::Escape($bad)) {
            throw "[CADDY_HTTP_TEST] Caddy log contains unexpected auto TLS marker: $bad"
        }
    }

    Write-Host "Caddyfile local HTTP fixture OK with caddy validate and HTTP GET."
} finally {
    if ($process -and -not $process.HasExited) {
        try {
            $process.Kill()
            $process.WaitForExit()
        } catch {
        }
    }
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
