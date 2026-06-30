$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$installScript = Join-Path $repoRoot "deploy\windows-native\scripts\install-services.ps1"
$commonScript = Join-Path $repoRoot "deploy\windows-native\scripts\common.ps1"

function Import-FunctionsFromFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$FunctionNames,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $tokens = $null
    $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) {
        $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber) $($_.Message)" }) -join "; "
        throw "[$Label] Parse failed: $details"
    }

    $functionAsts = $ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $FunctionNames -contains $node.Name
    }, $true)

    foreach ($name in $FunctionNames) {
        $match = $functionAsts | Where-Object { $_.Name -eq $name } | Select-Object -First 1
        if (-not $match) {
            throw "[$Label] Missing function: $name"
        }
        Invoke-Expression $match.Extent.Text
    }
}

Import-FunctionsFromFile `
    -Path $commonScript `
    -FunctionNames @("Protect-Text") `
    -Label "NATIVE_RUNNER_TEST"

Import-FunctionsFromFile `
    -Path $installScript `
    -FunctionNames @(
        "Format-CommandForLog",
        "Get-TextTail",
        "Get-CommandFailureArtifactPath",
        "Save-CommandFailureArtifact",
        "ConvertTo-StartProcessArgumentString",
        "Invoke-LoggedCommand"
    ) `
    -Label "NATIVE_RUNNER_TEST"

$Script:LastInstallStep = "native-command-runner-test"
$Script:NativeRunnerLogDir = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-native-runner-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Script:NativeRunnerLogDir -Force | Out-Null

function Get-LogsDir {
    return $Script:NativeRunnerLogDir
}

function Get-NativeLogPath {
    param([Parameter(Mandatory = $true)][string]$Name)
    return (Join-Path $Script:NativeRunnerLogDir $Name)
}

function Write-InstallLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$LogName = "runner.log"
    )

    $line = "[test] {0}" -f (Protect-Text $Message)
    Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value $line -Encoding UTF8
}

function Get-CurrentPowerShellPath {
    if ($PSVersionTable.PSEdition -eq "Desktop") {
        $desktop = Join-Path $PSHOME "powershell.exe"
        if (Test-Path -LiteralPath $desktop -PathType Leaf) {
            return $desktop
        }
    }

    $processPath = ""
    try {
        $processPath = [string](Get-Process -Id $PID).Path
    } catch {
    }
    if (-not [string]::IsNullOrWhiteSpace($processPath) -and (Test-Path -LiteralPath $processPath -PathType Leaf)) {
        return $processPath
    }

    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($pwsh -and -not [string]::IsNullOrWhiteSpace([string]$pwsh.Source)) {
        return [string]$pwsh.Source
    }

    $powershell = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if ($powershell -and -not [string]::IsNullOrWhiteSpace([string]$powershell.Source)) {
        return [string]$powershell.Source
    }

    throw "[NATIVE_RUNNER_TEST] Could not resolve a PowerShell executable."
}

function New-PowerShellCommandArgs {
    param([Parameter(Mandatory = $true)][string]$Command)

    $args = @("-NoProfile")
    if ($PSVersionTable.PSEdition -eq "Desktop") {
        $args += @("-ExecutionPolicy", "Bypass")
    }
    $args += @("-Command", $Command)
    return $args
}

function Get-RunnerLog {
    $path = Get-NativeLogPath "runner.log"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return ""
    }
    return Get-Content -LiteralPath $path -Raw
}

function Assert-LogContains {
    param(
        [Parameter(Mandatory = $true)][string]$Needle,
        [string]$Message = "missing expected log token"
    )

    $log = Get-RunnerLog
    if (-not $log.Contains($Needle)) {
        throw "[NATIVE_RUNNER_TEST] $Message`: $Needle"
    }
}

$shell = Get-CurrentPowerShellPath
$cwdWithSpace = Join-Path $Script:NativeRunnerLogDir "cwd with space"
New-Item -ItemType Directory -Path $cwdWithSpace -Force | Out-Null
$secret = "runner-secret-" + [Guid]::NewGuid().ToString("N")

try {
    Invoke-LoggedCommand `
        -FilePath $shell `
        -ArgumentList (New-PowerShellCommandArgs -Command "Write-Output 'stdout-ok'; exit 0") `
        -LogName "runner.log"
    Assert-LogContains -Needle "stdout-ok" -Message "stdout exit 0 was not logged"
    Assert-LogContains -Needle "EXIT_CODE 0" -Message "exit 0 was not logged"

    Invoke-LoggedCommand `
        -FilePath $shell `
        -ArgumentList (New-PowerShellCommandArgs -Command "[Console]::Error.WriteLine('stderr-ok'); exit 0") `
        -LogName "runner.log"
    Assert-LogContains -Needle "stderr-ok" -Message "stderr exit 0 was not logged"
    Assert-LogContains -Needle "COMMAND_STDERR_NONFATAL" -Message "stderr exit 0 was not marked nonfatal"

    Invoke-LoggedCommand `
        -FilePath $shell `
        -ArgumentList (New-PowerShellCommandArgs -Command "Write-Output 'stdout-mixed'; [Console]::Error.WriteLine('stderr-mixed'); exit 0") `
        -LogName "runner.log"
    Assert-LogContains -Needle "stdout-mixed" -Message "mixed stdout was not logged"
    Assert-LogContains -Needle "stderr-mixed" -Message "mixed stderr was not logged"

    $failed = $false
    try {
        Invoke-LoggedCommand `
            -FilePath $shell `
            -ArgumentList (New-PowerShellCommandArgs -Command "[Console]::Error.WriteLine('stderr-exit5'); exit 5") `
            -LogName "runner.log"
    } catch {
        $failed = $true
        if ($_.Exception.Message -notmatch "codigo 5") {
            throw "[NATIVE_RUNNER_TEST] exit 5 did not surface the real exit code: $($_.Exception.Message)"
        }
    }
    if (-not $failed) {
        throw "[NATIVE_RUNNER_TEST] stderr exit 5 did not fail."
    }
    Assert-LogContains -Needle "COMMAND_FAILED exitCode=5" -Message "exit 5 failure was not logged"
    $failedStderr = Join-Path $Script:NativeRunnerLogDir "failed-native-command-runner-test-stderr.log"
    if (-not (Test-Path -LiteralPath $failedStderr -PathType Leaf)) {
        throw "[NATIVE_RUNNER_TEST] failed stderr artifact was not preserved."
    }
    if (-not (Get-Content -LiteralPath $failedStderr -Raw).Contains("stderr-exit5")) {
        throw "[NATIVE_RUNNER_TEST] failed stderr artifact does not contain stderr tail."
    }

    Invoke-LoggedCommand `
        -FilePath $shell `
        -ArgumentList (New-PowerShellCommandArgs -Command "if (`$env:TEST_RUNNER_VALUE -ne 'expected value') { [Console]::Error.WriteLine('env mismatch'); exit 6 }; Write-Output 'env-ok'; exit 0") `
        -Environment @{ TEST_RUNNER_VALUE = "expected value" } `
        -LogName "runner.log"
    Assert-LogContains -Needle "env-ok" -Message "temporary environment was not applied"

    Invoke-LoggedCommand `
        -FilePath $shell `
        -ArgumentList (New-PowerShellCommandArgs -Command "if ((Get-Location).Path -ne `$env:EXPECTED_CWD) { [Console]::Error.WriteLine('cwd mismatch ' + (Get-Location).Path); exit 7 }; Write-Output 'cwd-ok'; exit 0") `
        -WorkingDirectory $cwdWithSpace `
        -Environment @{ EXPECTED_CWD = $cwdWithSpace } `
        -LogName "runner.log"
    Assert-LogContains -Needle "cwd-ok" -Message "working directory with spaces was not honored"

    Invoke-LoggedCommand `
        -FilePath $shell `
        -ArgumentList (New-PowerShellCommandArgs -Command "Write-Output ('password=' + `$env:TEST_SECRET_VALUE); [Console]::Error.WriteLine('token=' + `$env:TEST_SECRET_VALUE); exit 0") `
        -Environment @{ TEST_SECRET_VALUE = $secret } `
        -LogName "runner.log"
    $log = Get-RunnerLog
    if ($log.Contains($secret)) {
        throw "[NATIVE_RUNNER_TEST] secret value leaked into runner log."
    }
    if (-not $log.Contains("***REDACTED***")) {
        throw "[NATIVE_RUNNER_TEST] redacted marker missing from runner log."
    }

    $tmpFiles = @(Get-ChildItem -LiteralPath $Script:NativeRunnerLogDir -Filter "*.tmp" -File -ErrorAction SilentlyContinue)
    if ($tmpFiles.Count -gt 0) {
        throw "[NATIVE_RUNNER_TEST] temporary stdout/stderr files were left behind."
    }

    Write-Host "Native command runner fixture OK; stderr exit 0 stayed nonfatal under ErrorActionPreference=Stop."
} finally {
    Remove-Item -LiteralPath $Script:NativeRunnerLogDir -Recurse -Force -ErrorAction SilentlyContinue
}
