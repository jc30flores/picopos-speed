$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
foreach($svc in $Script:Services){ $s=Get-ServiceSafe $svc; if($s){ Start-Service $svc; Write-SafeHost "Iniciado $svc" } else { Write-SafeHost "No instalado $svc" } }
