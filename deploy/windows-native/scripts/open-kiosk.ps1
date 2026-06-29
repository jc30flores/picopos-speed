param(
    [switch]$AppMode,
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

function Write-KioskLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-NativeLog -LogName "open-kiosk.log" -Message $Message
}

function Get-EdgePath {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles(x86)})) {
        $candidates += (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe")
    }
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $candidates += (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe")
    }
    return ($candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1)
}

$appUrl = Get-AppUrl
$readyUrl = "$appUrl/api/health/ready/"
Write-KioskLog "OPEN_KIOSK_BEGIN url=$appUrl appMode=$AppMode"

if (-not (Wait-HttpOk -Uri $readyUrl -Name "open-kiosk-ready" -LogName "open-kiosk.log" -TimeoutSeconds $TimeoutSeconds)) {
    throw "Pico de Gallo no esta listo para abrir: $readyUrl"
}

$edge = Get-EdgePath
if (-not [string]::IsNullOrWhiteSpace($edge)) {
    if ($AppMode) {
        Write-KioskLog "OPEN_EDGE_APP path=$edge"
        Start-Process -FilePath $edge -ArgumentList @("--app=$appUrl") | Out-Null
        exit 0
    }

    try {
        Write-KioskLog "OPEN_EDGE_KIOSK path=$edge"
        Start-Process -FilePath $edge -ArgumentList @("--kiosk", $appUrl, "--edge-kiosk-type=fullscreen") | Out-Null
        exit 0
    } catch {
        Write-KioskLog "OPEN_EDGE_KIOSK_FAILED $($_.Exception.Message)"
        Write-KioskLog "OPEN_EDGE_APP path=$edge"
        Start-Process -FilePath $edge -ArgumentList @("--app=$appUrl") | Out-Null
        exit 0
    }
}

Write-KioskLog "OPEN_DEFAULT_BROWSER url=$appUrl"
Start-Process $appUrl | Out-Null
