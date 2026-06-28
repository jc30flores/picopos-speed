param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot 'runtime-manifest.json'),
    [string]$OutputDir = 'release/runtime-cache'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Fail([string]$Message) { throw "[fetch-runtimes] $Message" }
function Assert-Https([string]$Url, [string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Url) -or -not $Url.StartsWith('https://')) { Fail "$Name debe usar URL HTTPS versionada." }
    if ($Url -match 'example\.invalid|/latest|bit\.ly|tinyurl|goo\.gl') { Fail "$Name tiene URL no válida para release: $Url" }
}
function Assert-Sha([string]$Sha, [string]$Name) {
    if ($Sha -notmatch '^[A-Fa-f0-9]{64}$') { Fail "$Name debe definir sha256 real de 64 caracteres hexadecimales." }
}

if (-not (Test-Path -LiteralPath $ManifestPath)) { Fail "No existe manifest de runtimes: $ManifestPath" }
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$out = New-Item -ItemType Directory -Path $OutputDir -Force
$resolved = [ordered]@{}
foreach ($prop in $manifest.runtimes.PSObject.Properties) {
    $name = $prop.Name
    $item = $prop.Value
    Assert-Https $item.url $name
    Assert-Sha $item.sha256 $name
    $download = Join-Path $out.FullName (Split-Path ([Uri]$item.url).AbsolutePath -Leaf)
    Write-Host "Descargando runtime verificado: $name $($item.version)"
    Invoke-WebRequest -Uri $item.url -OutFile $download -UseBasicParsing
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $download).Hash.ToLowerInvariant()
    if ($actual -ne $item.sha256.ToLowerInvariant()) { Fail "SHA256 inválido para $name. Esperado $($item.sha256), obtenido $actual" }
    $target = Join-Path $out.FullName $item.extractTo
    if ($item.archiveType -eq 'zip') {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        Expand-Archive -LiteralPath $download -DestinationPath $target -Force
        if ($item.expectedExecutable) { $resolved[$name] = (Join-Path $target $item.expectedExecutable) } else { $resolved[$name] = $target }
    } elseif ($item.archiveType -eq 'file') {
        $targetFile = Join-Path $out.FullName $item.extractTo
        Copy-Item -LiteralPath $download -Destination $targetFile -Force
        $resolved[$name] = $targetFile
    } elseif ($item.archiveType -eq 'installer') {
        $resolved[$name] = $download
    } else {
        Fail "archiveType no soportado para ${name}: $($item.archiveType)"
    }
}
$resolvedPath = Join-Path $out.FullName 'resolved-runtimes.json'
$resolved | ConvertTo-Json -Depth 4 | Set-Content -Path $resolvedPath -Encoding UTF8
Write-Host "Runtimes verificados en $($out.FullName)"
Write-Host "Resolved manifest: $resolvedPath"
