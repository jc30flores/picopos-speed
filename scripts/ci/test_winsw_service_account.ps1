$ErrorActionPreference = "Stop"

$isWindowsRuntime = $false
if ($PSVersionTable.PSEdition -eq "Desktop") {
    $isWindowsRuntime = $true
} elseif (Get-Variable -Name IsWindows -Scope Global -ErrorAction SilentlyContinue) {
    $isWindowsRuntime = [bool]$IsWindows
}

if (-not $isWindowsRuntime) {
    Write-Host "WinSW service account fixture skipped: non-Windows runner."
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "WinSW service account fixture skipped: Windows runner is not elevated."
    exit 0
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$installScript = Join-Path $repoRoot "deploy\windows-native\scripts\install-services.ps1"

$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($installScript, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {
    $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber) $($_.Message)" }) -join "; "
    throw "[WINSW_ACCOUNT_TEST] Parse failed: $details"
}

$functionNames = @(
    "Format-CommandForLog",
    "ConvertTo-StartProcessArgumentString",
    "Invoke-LoggedSecretCommand",
    "Get-ServiceLogonNativeApi",
    "Get-PicoServiceAccountLogonName",
    "Test-PostgresServiceAccountStartName",
    "Set-WindowsServiceLogonAccountSafe"
)

$functionAsts = $ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $functionNames -contains $node.Name
}, $true)

foreach ($name in $functionNames) {
    $match = $functionAsts | Where-Object { $_.Name -eq $name } | Select-Object -First 1
    if (-not $match) {
        throw "[WINSW_ACCOUNT_TEST] Missing function: $name"
    }
    Invoke-Expression $match.Extent.Text
}

$Script:PicoServiceAccountName = "PicoDeGalloSvcTest"
$Script:WinSWAccountTestLog = @()
$Script:WinSWAccountTestLogDir = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-winsw-account-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Script:WinSWAccountTestLogDir -Force | Out-Null

function Write-InstallLog {
    param(
        [string]$Message,
        [string]$LogName = "test.log"
    )
    $Script:WinSWAccountTestLog += "$LogName $Message"
}

function Get-LogsDir {
    return $Script:WinSWAccountTestLogDir
}

function Get-NativeLogPath {
    param([Parameter(Mandatory = $true)][string]$Name)
    return (Join-Path $Script:WinSWAccountTestLogDir $Name)
}

function Protect-Text {
    param([string]$Text)
    if ($null -eq $Text) { return "" }
    return $Text
}

function Get-ServiceStartNameSafe {
    param([Parameter(Mandatory = $true)][string]$Name)
    try {
        $escaped = $Name.Replace("'", "''")
        $service = Get-CimInstance Win32_Service -Filter "Name='$escaped'" -ErrorAction Stop
        if ($service -and -not [string]::IsNullOrWhiteSpace([string]$service.StartName)) {
            return [string]$service.StartName
        }
    } catch {
        return "unknown"
    }
    return "unknown"
}

$serviceName = "PicoDeGallo-WinSW-Account-Test"
$testUser = $Script:PicoServiceAccountName
$password = "Pico" + ([Guid]::NewGuid().ToString("N").Substring(0, 24)) + "Aa1"
$scExe = Join-Path $env:SystemRoot "System32\sc.exe"

function Remove-TestService {
    param([string]$Name)
    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne "Stopped") {
        Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
    }
    if (Get-CimInstance Win32_Service -Filter "Name='$Name'" -ErrorAction SilentlyContinue) {
        & $scExe delete $Name | Out-Null
        for ($i = 0; $i -lt 30; $i++) {
            if (-not (Get-CimInstance Win32_Service -Filter "Name='$Name'" -ErrorAction SilentlyContinue)) {
                break
            }
            Start-Sleep -Seconds 1
        }
    }
}

function Remove-TestUser {
    param([string]$Name)
    if (Get-Command Remove-LocalUser -ErrorAction SilentlyContinue) {
        try {
            Remove-LocalUser -Name $Name -ErrorAction Stop
            return
        } catch {
        }
    }
    & (Join-Path $env:SystemRoot "System32\net.exe") user $Name /delete *> $null
}

try {
    Remove-TestService -Name $serviceName
    Remove-TestUser -Name $testUser

    $securePassword = ConvertTo-SecureString $password -AsPlainText -Force
    if (Get-Command New-LocalUser -ErrorAction SilentlyContinue) {
        New-LocalUser `
            -Name $testUser `
            -Password $securePassword `
            -Description "Pico service account test" `
            -PasswordNeverExpires `
            -UserMayNotChangePassword `
            -ErrorAction Stop | Out-Null
    } else {
        & (Join-Path $env:SystemRoot "System32\net.exe") user $testUser $password /add /expires:never /y | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "[WINSW_ACCOUNT_TEST] net user failed."
        }
    }

    $binPath = (Join-Path $env:SystemRoot "System32\cmd.exe") + " /c ping -n 60 127.0.0.1 > nul"
    & $scExe create $serviceName binPath= $binPath start= demand | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "[WINSW_ACCOUNT_TEST] sc create failed."
    }

    Set-WindowsServiceLogonAccountSafe `
        -ServiceId $serviceName `
        -AccountName (Get-PicoServiceAccountLogonName) `
        -Password $password

    $startName = Get-ServiceStartNameSafe -Name $serviceName
    if (-not (Test-PostgresServiceAccountStartName -StartName $startName)) {
        throw "[WINSW_ACCOUNT_TEST] Service StartName was not changed to PicoDeGalloSvcTest: $startName"
    }
    if ($startName -ieq "LocalSystem") {
        throw "[WINSW_ACCOUNT_TEST] Service stayed LocalSystem."
    }

    foreach ($line in $Script:WinSWAccountTestLog) {
        if ($line.Contains($password)) {
            throw "[WINSW_ACCOUNT_TEST] Password leaked into test log."
        }
    }

    Write-Host "WinSW service account fixture OK StartName=$startName"
} finally {
    Remove-TestService -Name $serviceName
    Remove-TestUser -Name $testUser
    Remove-Item -LiteralPath $Script:WinSWAccountTestLogDir -Recurse -Force -ErrorAction SilentlyContinue
}
