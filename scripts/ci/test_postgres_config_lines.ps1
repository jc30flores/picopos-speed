$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$installScript = Join-Path $repoRoot "deploy\windows-native\scripts\install-services.ps1"

$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($installScript, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {
    $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber) $($_.Message)" }) -join "; "
    throw "[POSTGRES_CONFIG_TEST] Parse failed: $details"
}

$functionNames = @(
    "Get-Utf8NoBomEncoding",
    "Get-BytePrefixHex",
    "Read-PostgresConfigLines",
    "Test-PostgresConfigEncoding",
    "Write-PostgresConfigText",
    "Write-PostgresConfigLines",
    "Set-PostgresConfigValue"
)

$functionAsts = $ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $functionNames -contains $node.Name
}, $true)

foreach ($name in $functionNames) {
    $match = $functionAsts | Where-Object { $_.Name -eq $name } | Select-Object -First 1
    if (-not $match) {
        throw "[POSTGRES_CONFIG_TEST] Missing function: $name"
    }
    Invoke-Expression $match.Extent.Text
}

$Script:PostgresConfigTestLog = @()
function Write-InstallLog {
    param(
        [string]$Message,
        [string]$LogName = "test.log"
    )
    $Script:PostgresConfigTestLog += "$LogName $Message"
}

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-postgres-config-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$conf = Join-Path $tempDir "postgresql.conf"

try {
    $fixture = @(
        "# PostgreSQL fixture",
        "",
        "#port = 5432",
        "",
        "listen_addresses = 'localhost'",
        "",
        "# trailing comment"
    )

    Write-PostgresConfigLines -Path $conf -Lines $fixture
    Set-PostgresConfigValue -ConfigPath $conf -Key "port" -Value "5432"
    Set-PostgresConfigValue -ConfigPath $conf -Key "listen_addresses" -Value "'127.0.0.1'"

    $lines = @(Read-PostgresConfigLines -Path $conf)
    if ($lines.Count -lt $fixture.Count) {
        throw "[POSTGRES_CONFIG_TEST] Fixture lines were unexpectedly lost."
    }
    if ($lines[1] -ne "" -or $lines[3] -ne "" -or $lines[5] -ne "") {
        throw "[POSTGRES_CONFIG_TEST] Blank lines were not preserved."
    }

    $text = [System.IO.File]::ReadAllText($conf, (Get-Utf8NoBomEncoding))
    if (-not $text.Contains("port = 5432")) {
        throw "[POSTGRES_CONFIG_TEST] port was not configured."
    }
    if (-not $text.Contains("listen_addresses = '127.0.0.1'")) {
        throw "[POSTGRES_CONFIG_TEST] listen_addresses was not configured."
    }
    if (-not $text.EndsWith("`r`n")) {
        throw "[POSTGRES_CONFIG_TEST] File does not end with CRLF newline."
    }

    [byte[]]$bytes = [System.IO.File]::ReadAllBytes($conf)
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        throw "[POSTGRES_CONFIG_TEST] UTF-16 LE BOM detected."
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        throw "[POSTGRES_CONFIG_TEST] UTF-16 BE BOM detected."
    }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        throw "[POSTGRES_CONFIG_TEST] UTF-8 BOM detected."
    }
    if ($bytes -contains 0) {
        throw "[POSTGRES_CONFIG_TEST] NUL byte detected."
    }

    Write-Host "PostgreSQL config blank-line fixture OK"
} finally {
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
