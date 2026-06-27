param([switch]$PurgeData)
. "$PSScriptRoot\common.ps1"
Assert-Admin
& "$PSScriptRoot\stop.ps1"
foreach($svc in $Script:Services){ if(Get-ServiceSafe $svc){ Write-SafeHost "Servicio para desinstalar: $svc" } }
if($PurgeData){ $answer=Read-Host 'Escribe BORRAR DATOS PICO DE GALLO para eliminar ProgramData'; if($answer -eq 'BORRAR DATOS PICO DE GALLO'){ Remove-Item $Script:ProgramDataDir -Recurse -Force; Write-Warning 'Datos eliminados.' } else { throw 'Purga cancelada.' } } else { Write-SafeHost 'Los datos se conservaron.' }
