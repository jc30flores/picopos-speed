$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Script:ProgramFilesDir = ${env:PICOPOS_PROGRAM_FILES_DIR}
if ([string]::IsNullOrWhiteSpace($Script:ProgramFilesDir)) {
    $Script:ProgramFilesDir = "C:\Program Files\PicoDeGallo"
}

$Script:ProgramDataDir = ${env:PICOPOS_PROGRAM_DATA_DIR}
if ([string]::IsNullOrWhiteSpace($Script:ProgramDataDir)) {
    $Script:ProgramDataDir = "C:\ProgramData\PicoDeGallo"
}

$Script:Services = @(
    "PicoDeGallo-PostgreSQL",
    "PicoDeGallo-Backend",
    "PicoDeGallo-DTE-Worker",
    "PicoDeGallo-DTE-Monitor",
    "PicoDeGallo-Caddy"
)
$Script:PicoServiceAccountName = "PicoDeGalloSvc"

function Get-EnvPath { Join-Path $Script:ProgramDataDir "config\.env" }
function Get-LogsDir { Join-Path $Script:ProgramDataDir "logs" }
function Get-BackupsDir { Join-Path $Script:ProgramDataDir "backups" }
function Get-DiagnosticsDir { Join-Path $Script:ProgramDataDir "diagnostics" }

function New-DirectorySafe {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Protect-Text {
    param([string]$Text)

    if ($null -eq $Text) { return "" }
    $out = $Text
    $patterns = @(
        "(?i)(password\s*[=:]\s*)[^\s;]+",
        "(?i)(secret\s*[=:]\s*)[^\s;]+",
        "(?i)(token\s*[=:]\s*)[^\s;]+",
        "(?i)(DB_PASSWORD\s*[=:]\s*)[^\s;]+",
        "(?i)(DJANGO_SECRET_KEY\s*[=:]\s*)[^\s;]+",
        "(?i)(DTE_API_TOKEN\s*[=:]\s*)[^\s;]+",
        "(?i)(PICO_BOOTSTRAP_ADMIN_PASSWORD\s*[=:]\s*)[^\s;]+",
        "(Authorization:\s*Bearer\s+)[^\s]+",
        "(Bearer\s+)[A-Za-z0-9._~+/-]+"
    )
    foreach ($pattern in $patterns) {
        $out = [regex]::Replace($out, $pattern, '$1***REDACTED***')
    }
    $out = [regex]::Replace($out, "(?is)(<password>).*?(</password>)", '$1***REDACTED***$2')
    return $out
}

function Write-SafeHost {
    param([string]$Message)
    Write-Host (Protect-Text $Message)
}

function Write-NativeLog {
    param(
        [Parameter(Mandatory = $true)][string]$LogName,
        [Parameter(Mandatory = $true)][string]$Message
    )

    New-DirectorySafe (Get-LogsDir)
    $line = "[{0}] {1}" -f (Get-Date -Format o), (Protect-Text $Message)
    Add-Content -LiteralPath (Join-Path (Get-LogsDir) $LogName) -Value $line -Encoding UTF8
}

function Read-NativeEnv {
    $map = [ordered]@{}
    $path = Get-EnvPath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return $map
    }

    Get-Content -LiteralPath $path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $map[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
    return $map
}

function Write-NativeEnv {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Map)

    New-DirectorySafe (Split-Path (Get-EnvPath) -Parent)
    $lines = @()
    foreach ($key in $Map.Keys) {
        $lines += "$key=$($Map[$key])"
    }
    [System.IO.File]::WriteAllLines((Get-EnvPath), $lines, [System.Text.UTF8Encoding]::new($false))
}

function New-RandomSecret {
    param([int]$Bytes = 32)

    if ($Bytes -lt 16) {
        throw "New-RandomSecret requiere al menos 16 bytes."
    }

    $bytesValue = [byte[]]::new($Bytes)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytesValue)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytesValue).Replace("+", "-").Replace("/", "_").TrimEnd("=")
}

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Ejecuta como Administrador."
    }
}

function Get-ServiceSafe {
    param([Parameter(Mandatory = $true)][string]$Name)
    Get-Service -Name $Name -ErrorAction SilentlyContinue
}

function Get-ServiceStartNameSafe {
    param([Parameter(Mandatory = $true)][string]$Name)

    try {
        $escaped = $Name.Replace("'", "''")
        $service = Get-CimInstance Win32_Service -Filter "Name='$escaped'" -ErrorAction Stop
        if ($service -and -not [string]::IsNullOrWhiteSpace([string]$service.StartName)) {
            return [string]$service.StartName
        }
    } catch {
        return "unknown"
    }
    return "unknown"
}

function Get-AppUrl {
    $envs = Read-NativeEnv
    $port = "9282"
    if ($envs.Contains("APP_HTTP_PORT") -and -not [string]::IsNullOrWhiteSpace([string]$envs["APP_HTTP_PORT"])) {
        $port = [string]$envs["APP_HTTP_PORT"]
    }
    return "http://127.0.0.1:$port"
}

function Test-TcpPort {
    param(
        [string]$HostName = "127.0.0.1",
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutMilliseconds = 2000
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne([TimeSpan]::FromMilliseconds($TimeoutMilliseconds))) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-TcpPort {
    param(
        [string]$HostName = "127.0.0.1",
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 60,
        [string]$LogName = "healthcheck.log"
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-TcpPort -HostName $HostName -Port $Port) {
            Write-NativeLog -LogName $LogName -Message "TCP_OK $HostName`:$Port"
            return $true
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-NativeLog -LogName $LogName -Message "TCP_FAILED $HostName`:$Port"
    return $false
}

function Test-DteEnv {
    $envs = Read-NativeEnv
    if ($envs["DTE_BACKGROUND_MODE"] -ne "external") {
        throw "DTE_BACKGROUND_MODE debe ser external."
    }
    if ([string]::IsNullOrWhiteSpace([string]$envs["DTE_BASE_URL"])) {
        throw "DTE_BASE_URL no puede quedar vacio."
    }
    if ([string]::IsNullOrWhiteSpace([string]$envs["DTE_API_TOKEN"])) {
        throw "DTE_API_TOKEN no puede quedar vacio."
    }
    return $true
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [string]$LogName = "healthcheck.log",
        [string]$Name = "http",
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            $status = [int]$response.StatusCode
            if ($status -ge 200 -and $status -lt 300) {
                Write-NativeLog -LogName $LogName -Message "HTTP_OK $Name $Uri status=$status"
                return $true
            }
            $lastError = "status=$status"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-NativeLog -LogName $LogName -Message "HTTP_FAILED $Name $Uri $lastError"
    return $false
}
