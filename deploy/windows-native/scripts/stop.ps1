$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

Assert-Admin

$ordered = @($Script:Services)
[array]::Reverse($ordered)

foreach ($svc in $ordered) {
    $service = Get-ServiceSafe $svc
    if (-not $service) {
        Write-SafeHost "$svc no instalado"
        continue
    }
    if ($service.Status -ne "Stopped") {
        Stop-Service -Name $svc -ErrorAction SilentlyContinue
        try {
            $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Stopped, [TimeSpan]::FromSeconds(90))
        } catch {
            Write-NativeLog -LogName "service-install.log" -Message "STOP_TIMEOUT $svc $($_.Exception.Message)"
        }
    }
    Write-NativeLog -LogName "service-install.log" -Message "STOPPED $svc"
    Write-SafeHost "Detenido $svc"
}
