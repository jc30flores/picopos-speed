param([switch]$RemoveImages, [switch]$PurgeData, [switch]$UseLocalBuild)
. "$PSScriptRoot\common.ps1"
Invoke-DockerCompose @('down') -UseLocalBuild:$UseLocalBuild | Out-Null
if ($RemoveImages) { Invoke-DockerCompose @('down','--rmi','local') -UseLocalBuild:$UseLocalBuild | Out-Null }
if ($PurgeData) {
    Write-Warning 'Esta acción eliminará postgres_data, media_data, static_data y dte_logs. Es irreversible.'
    if (-not (Confirm-Danger 'Escribe BORRAR DATOS PICO DE GALLO para confirmar' $Script:RequiredPhrase)) { throw 'Purga cancelada.' }
    Invoke-DockerCompose @('down','-v') -UseLocalBuild:$UseLocalBuild | Out-Null
    Write-Warning 'Datos eliminados.'
} else {
    Write-SafeHost 'Los datos se conservaron.'
}
