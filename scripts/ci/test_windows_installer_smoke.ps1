$ErrorActionPreference = "Stop"

$isWindowsHost = ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT)
if (-not $isWindowsHost) {
    Write-Host "[WINDOWS_INSTALLER_SMOKE] SKIP non-Windows host."
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[WINDOWS_INSTALLER_SMOKE] SKIP administrator privileges are required."
    exit 0
}

if ($env:RUN_WINDOWS_INSTALLER_SMOKE -ne "1") {
    Write-Host "[WINDOWS_INSTALLER_SMOKE] SKIP set RUN_WINDOWS_INSTALLER_SMOKE=1 to install services on this machine."
    exit 0
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$version = if ([string]::IsNullOrWhiteSpace($env:PICO_INSTALLER_SMOKE_VERSION)) { "0.1.12-test" } else { $env:PICO_INSTALLER_SMOKE_VERSION }
$installer = $env:PICO_INSTALLER_SMOKE_EXE
if ([string]::IsNullOrWhiteSpace($installer)) {
    $installer = Join-Path $repoRoot "release\installers\PicoDeGallo-Setup-$version.exe"
}
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    Write-Host "[WINDOWS_INSTALLER_SMOKE] SKIP installer not found: $installer"
    exit 0
}

Write-Host "[WINDOWS_INSTALLER_SMOKE] Installing $installer"
$process = Start-Process -FilePath $installer -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait -PassThru
if ([int]$process.ExitCode -ne 0) {
    throw "[WINDOWS_INSTALLER_SMOKE] installer failed with exit code $($process.ExitCode)"
}

$programFilesDir = if ([string]::IsNullOrWhiteSpace($env:PICOPOS_PROGRAM_FILES_DIR)) { "C:\Program Files\PicoDeGallo" } else { $env:PICOPOS_PROGRAM_FILES_DIR }
$programDataDir = if ([string]::IsNullOrWhiteSpace($env:PICOPOS_PROGRAM_DATA_DIR)) { "C:\ProgramData\PicoDeGallo" } else { $env:PICOPOS_PROGRAM_DATA_DIR }
$statusScript = Join-Path $programFilesDir "scripts\status.ps1"
$diagnosticsScript = Join-Path $programFilesDir "scripts\diagnostics.ps1"

foreach ($path in @(
    (Join-Path $programFilesDir "version.json"),
    (Join-Path $programDataDir "install-state.json"),
    (Join-Path $programDataDir "config\runtime-ports.json"),
    $statusScript
)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "[WINDOWS_INSTALLER_SMOKE] required file missing: $path"
    }
}

& $statusScript
if ($LASTEXITCODE -ne 0) {
    throw "[WINDOWS_INSTALLER_SMOKE] status.ps1 failed."
}

if (Test-Path -LiteralPath $diagnosticsScript -PathType Leaf) {
    & $diagnosticsScript
}

Write-Host "[WINDOWS_INSTALLER_SMOKE] OK"
