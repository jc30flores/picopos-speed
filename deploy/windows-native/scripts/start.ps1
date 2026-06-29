$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
Assert-Admin

foreach ($svc in $Script:Services) {
    $service = Get-ServiceSafe $svc
    if (-not $service) {
        throw "Servicio requerido no instalado: $svc"
    }
    if ($service.Status -ne "Running") {
        Start-Service $svc
        $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Running, [TimeSpan]::FromSeconds(90))
    }
    Write-SafeHost "Iniciado $svc"
}
