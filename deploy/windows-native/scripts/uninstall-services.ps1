param([switch]$PurgeData)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

Assert-Admin

& "$PSScriptRoot\stop.ps1"

$serviceDir = Join-Path $Script:ProgramFilesDir "services"
$ordered = @($Script:Services)
[array]::Reverse($ordered)

foreach ($svc in $ordered) {
    if (-not (Get-ServiceSafe $svc)) {
        continue
    }

    $wrapper = Join-Path $serviceDir "$svc.exe"
    if (Test-Path -LiteralPath $wrapper -PathType Leaf) {
        & $wrapper uninstall
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudo desinstalar servicio $svc."
        }
        Write-SafeHost "Servicio desinstalado: $svc"
    } else {
        Write-Warning "Servicio $svc existe, pero falta wrapper $wrapper."
    }
}

if ($PurgeData) {
    $answer = Read-Host "Escribe BORRAR DATOS PICO DE GALLO para eliminar ProgramData"
    $confirm = Read-Host "Repite BORRAR DATOS PICO DE GALLO para confirmar"
    if ($answer -eq "BORRAR DATOS PICO DE GALLO" -and $confirm -eq "BORRAR DATOS PICO DE GALLO") {
        Remove-Item -LiteralPath $Script:ProgramDataDir -Recurse -Force
        Write-Warning "Datos eliminados."
    } else {
        throw "Purga cancelada."
    }
} else {
    Write-SafeHost "Los datos se conservaron."
}
