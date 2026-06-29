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

Start-NativeService "PicoDeGallo-PostgreSQL"
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
