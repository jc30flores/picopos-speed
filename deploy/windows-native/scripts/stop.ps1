. "$PSScriptRoot\common.ps1"
$ordered = @($Script:Services); [array]::Reverse($ordered)
foreach($svc in $ordered){ $s=Get-ServiceSafe $svc; if($s){ Stop-Service $svc -ErrorAction SilentlyContinue; Write-SafeHost "Detenido $svc" } }
