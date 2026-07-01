$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

Assert-Admin

function Start-NativeService {
    param([Parameter(Mandatory = $true)][string]$Name)

    $service = Get-ServiceSafe $Name
    if (-not $service) {
        throw "Servicio requerido no instalado: $Name"
    }

    if ($service.Status -ne "Running") {
        Start-Service -Name $Name
        $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Running, [TimeSpan]::FromSeconds(90))
    }
    Write-NativeLog -LogName "service-install.log" -Message "STARTED $Name"
    Write-SafeHost "Iniciado $Name"
}

function Show-NativeLogTail {
    param(
        [Parameter(Mandatory = $true)][string]$LogName,
        [int]$Lines = 80
    )

    $path = Join-Path (Get-LogsDir) $LogName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return
    }
    Write-SafeHost "----- $LogName -----"
    Get-Content -LiteralPath $path -Tail $Lines -ErrorAction SilentlyContinue |
        ForEach-Object { Write-SafeHost ([string]$_) }
}

function Show-PostgresStartupDiagnostics {
    foreach ($logName in @(
        "postgres-foreground-test.err.log",
        "postgres-foreground-test.out.log",
        "PicoDeGallo-PostgreSQL.err.log",
        "PicoDeGallo-PostgreSQL.wrapper.log",
        "postgres-service.log"
    )) {
        Show-NativeLogTail -LogName $logName -Lines 80
    }
}

try {
    Start-NativeService "PicoDeGallo-PostgreSQL"
} catch {
    Show-PostgresStartupDiagnostics
    throw
}

$envs = Read-NativeEnv
$dbHost = if ([string]::IsNullOrWhiteSpace([string]$envs["DB_HOST"])) { "127.0.0.1" } else { [string]$envs["DB_HOST"] }
$dbPort = if ([string]::IsNullOrWhiteSpace([string]$envs["DB_PORT"])) { 5432 } else { [int]$envs["DB_PORT"] }
if (-not (Wait-TcpPort -HostName $dbHost -Port $dbPort -TimeoutSeconds 60)) {
    Show-PostgresStartupDiagnostics
    throw "PostgreSQL no quedo escuchando en $dbHost`:$dbPort"
}
Start-NativeService "PicoDeGallo-Backend"
Wait-HttpOk -Uri "http://127.0.0.1:8000/api/health/ready/" -Name "backend-ready-direct" -TimeoutSeconds 120 | Out-Null
Start-NativeService "PicoDeGallo-DTE-Worker"
Start-NativeService "PicoDeGallo-DTE-Monitor"
Start-NativeService "PicoDeGallo-Caddy"

$appUrl = Get-AppUrl
if (-not (Wait-HttpOk -Uri "$appUrl/api/health/live/" -Name "health-live" -TimeoutSeconds 120)) {
    throw "Health live no respondio en $appUrl"
}
if (-not (Wait-HttpOk -Uri "$appUrl/api/health/ready/" -Name "health-ready" -TimeoutSeconds 120)) {
    throw "Health ready no respondio en $appUrl"
}
