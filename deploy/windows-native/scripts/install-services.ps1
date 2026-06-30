$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

New-DirectorySafe (Get-LogsDir)
$Script:InstallPhase = "bootstrap"
$Script:LastInstallStep = "bootstrap"
$Script:InstallTranscriptStarted = $false
$Script:BuiltinAdminGroupSid = "S-1-5-32-544"
$Script:BuiltinStandardGroupSid = "S-1-5-32-545"

function Get-RequiredEnvValue {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Map,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $value = [string]$Map[$Name]
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Falta $Name en configuracion nativa."
    }
    return $value
}

function Get-NativeLogPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    New-DirectorySafe (Get-LogsDir)
    return (Join-Path (Get-LogsDir) $Name)
}

function Write-InstallLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$LogName = "install-services.log"
    )

    $line = "[{0}] {1}" -f (Get-Date -Format o), (Protect-Text $Message)
    Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value $line -Encoding UTF8
}

function Start-InstallTranscriptSafe {
    $path = Get-NativeLogPath "install-services-transcript.log"
    try {
        Start-Transcript -Path $path -Append -Force -ErrorAction Stop | Out-Null
        $Script:InstallTranscriptStarted = $true
        Write-InstallLog "TRANSCRIPT_STARTED path=$path"
    } catch {
        Write-InstallLog "TRANSCRIPT_SKIPPED reason=$($_.Exception.Message)"
    }
}

function Stop-InstallTranscriptSafe {
    if (-not $Script:InstallTranscriptStarted) {
        return
    }
    try {
        Stop-Transcript | Out-Null
    } catch {
    }
    $Script:InstallTranscriptStarted = $false
}

function Write-InstallException {
    param([Parameter(Mandatory = $true)]$ErrorRecord)

    $exception = $ErrorRecord.Exception
    $invocation = $ErrorRecord.InvocationInfo
    $lines = @(
        "INSTALL_SERVICES_FAILED",
        "phase=$Script:InstallPhase",
        "lastStep=$Script:LastInstallStep",
        ("exceptionType={0}" -f $exception.GetType().FullName),
        ("message={0}" -f $exception.Message)
    )
    if ($invocation) {
        $lines += ("scriptName={0}" -f $invocation.ScriptName)
        $lines += ("line={0}" -f $invocation.ScriptLineNumber)
        $lines += ("offset={0}" -f $invocation.OffsetInLine)
        if (-not [string]::IsNullOrWhiteSpace([string]$invocation.PositionMessage)) {
            $lines += "positionMessage_BEGIN"
            $lines += [string]$invocation.PositionMessage
            $lines += "positionMessage_END"
        }
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$ErrorRecord.ScriptStackTrace)) {
        $lines += "scriptStackTrace_BEGIN"
        $lines += [string]$ErrorRecord.ScriptStackTrace
        $lines += "scriptStackTrace_END"
    }

    $message = ($lines -join "`n")
    Write-InstallLog -LogName "install-services.log" -Message $message
    Write-InstallLog -LogName "install-services-error.log" -Message $message
}

function Invoke-InstallStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$ScriptBlock
    )

    $Script:InstallPhase = $Name
    $Script:LastInstallStep = $Name
    Write-InstallLog "STEP_BEGIN $Name"
    try {
        & $ScriptBlock
        Write-InstallLog "STEP_SUCCESS $Name"
    } catch {
        Write-InstallLog -LogName "install-services.log" -Message ("STEP_ERROR $Name " + $_.Exception.Message)
        Write-InstallLog -LogName "install-services-error.log" -Message ("STEP_ERROR $Name " + $_.Exception.Message)
        throw
    }
}

function Format-CommandForLog {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    $parts = @($FilePath) + $ArgumentList
    $quoted = foreach ($part in $parts) {
        $text = [string]$part
        if ($text -match '\s') {
            '"' + $text.Replace('"', '\"') + '"'
        } else {
            $text
        }
    }
    return ($quoted -join " ")
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][string]$LogName,
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{},
        [switch]$ReturnStdout
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "No existe ejecutable requerido: $FilePath"
    }

    $logPath = Get-NativeLogPath $LogName
    $stdout = Join-Path (Get-LogsDir) ("{0}.stdout.tmp" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path (Get-LogsDir) ("{0}.stderr.tmp" -f ([Guid]::NewGuid().ToString("N")))
    $oldEnvironment = @{}
    $exitCode = 0

    Write-InstallLog -LogName $LogName -Message ("RUN " + (Format-CommandForLog -FilePath $FilePath -ArgumentList $ArgumentList))

    try {
        foreach ($name in $Environment.Keys) {
            $oldEnvironment[$name] = [Environment]::GetEnvironmentVariable([string]$name, "Process")
            [Environment]::SetEnvironmentVariable([string]$name, [string]$Environment[$name], "Process")
        }

        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            Push-Location $WorkingDirectory
        }

        try {
            & $FilePath @ArgumentList > $stdout 2> $stderr
            $exitCode = $LASTEXITCODE
        } catch {
            Write-InstallLog -LogName $LogName -Message ("FAILED_TO_LAUNCH " + $_.Exception.Message)
            throw
        } finally {
            if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
                Pop-Location
            }
        }
    } finally {
        foreach ($name in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable([string]$name, $oldEnvironment[$name], "Process")
        }
    }

    $stdoutText = ""
    $stderrText = ""
    if (Test-Path -LiteralPath $stdout -PathType Leaf) {
        $stdoutText = Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stdoutText)) {
            Add-Content -LiteralPath $logPath -Value (Protect-Text $stdoutText) -Encoding UTF8
        }
    }
    if (Test-Path -LiteralPath $stderr -PathType Leaf) {
        $stderrText = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
            Add-Content -LiteralPath $logPath -Value (Protect-Text $stderrText) -Encoding UTF8
        }
    }

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    Write-InstallLog -LogName $LogName -Message ("EXIT_CODE " + $exitCode)
    if ($exitCode -ne 0) {
        throw "Comando fallo con codigo $exitCode. Revise $logPath"
    }

    if ($ReturnStdout) {
        return $stdoutText
    }
}

function Render-Template {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][hashtable]$Tokens
    )

    $content = Get-Content -LiteralPath $Source -Raw
    foreach ($key in $Tokens.Keys) {
        $content = $content.Replace("{{$key}}", [string]$Tokens[$key])
    }
    Set-Content -LiteralPath $Destination -Value $content -Encoding UTF8
}

function Get-ServiceWrapperPath {
    param([Parameter(Mandatory = $true)][string]$ServiceId)
    return (Join-Path (Join-Path $Script:ProgramFilesDir "services") "$ServiceId.exe")
}

function Invoke-WinSWCommand {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [Parameter(Mandatory = $true)][string]$Command
    )

    $wrapper = Get-ServiceWrapperPath -ServiceId $ServiceId
    Invoke-LoggedCommand `
        -FilePath $wrapper `
        -ArgumentList @($Command) `
        -LogName "service-install.log"
}

function Invoke-LoggedSecretCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string[]]$SafeArgumentList = @(),
        [string[]]$SecretValues = @(),
        [Parameter(Mandatory = $true)][string]$LogName,
        [string]$WorkingDirectory
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "No existe ejecutable requerido: $FilePath"
    }
    if ($SafeArgumentList.Count -eq 0) {
        throw "Invoke-LoggedSecretCommand requiere SafeArgumentList."
    }

    $logPath = Get-NativeLogPath $LogName
    $stdout = Join-Path (Get-LogsDir) ("{0}.stdout.tmp" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path (Get-LogsDir) ("{0}.stderr.tmp" -f ([Guid]::NewGuid().ToString("N")))
    Write-InstallLog -LogName $LogName -Message ("RUN_SECRET " + (Format-CommandForLog -FilePath $FilePath -ArgumentList $SafeArgumentList))

    $startParams = @{
        FilePath = $FilePath
        ArgumentList = (ConvertTo-StartProcessArgumentString -ArgumentList $ArgumentList)
        Wait = $true
        PassThru = $true
        RedirectStandardOutput = $stdout
        RedirectStandardError = $stderr
        WindowStyle = "Hidden"
    }
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $startParams.WorkingDirectory = $WorkingDirectory
    }

    $process = Start-Process @startParams
    $exitCode = [int]$process.ExitCode
    foreach ($path in @($stdout, $stderr)) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $text = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
            foreach ($secret in $SecretValues) {
                if (-not [string]::IsNullOrEmpty($secret)) {
                    $text = $text.Replace($secret, "***REDACTED***")
                }
            }
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                Add-Content -LiteralPath $logPath -Value (Protect-Text $text) -Encoding UTF8
            }
        }
    }
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    Write-InstallLog -LogName $LogName -Message ("EXIT_CODE " + $exitCode)
    if ($exitCode -ne 0) {
        throw "Comando secreto fallo con codigo $exitCode. Revise $logPath"
    }
}

function New-SecureRandomPassword {
    param([int]$Length = 32)

    if ($Length -lt 20) {
        throw "New-SecureRandomPassword requiere al menos 20 caracteres."
    }

    $upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    $lower = "abcdefghijkmnopqrstuvwxyz"
    $digits = "23456789"
    $symbols = "!#$%+-_"
    $all = $upper + $lower + $digits + $symbols
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()

    function Get-RandomIndex {
        param(
            [Parameter(Mandatory = $true)]$Generator,
            [Parameter(Mandatory = $true)][int]$MaxExclusive
        )

        $bytes = [byte[]]::new(4)
        $max = [uint64]$MaxExclusive
        $uintMax = [uint64]([uint32]::MaxValue)
        $limit = $uintMax - ($uintMax % $max)
        do {
            $Generator.GetBytes($bytes)
            $value = [uint64][BitConverter]::ToUInt32($bytes, 0)
        } while ($value -ge $limit)
        return [int]($value % $max)
    }

    function Get-RandomChar {
        param(
            [Parameter(Mandatory = $true)]$Generator,
            [Parameter(Mandatory = $true)][string]$Characters
        )
        return $Characters[(Get-RandomIndex -Generator $Generator -MaxExclusive $Characters.Length)]
    }

    try {
        $chars = New-Object "System.Collections.Generic.List[char]"
        foreach ($set in @($upper, $lower, $digits, $symbols)) {
            $chars.Add((Get-RandomChar -Generator $rng -Characters $set)) | Out-Null
        }
        while ($chars.Count -lt $Length) {
            $chars.Add((Get-RandomChar -Generator $rng -Characters $all)) | Out-Null
        }
        for ($i = $chars.Count - 1; $i -gt 0; $i--) {
            $j = Get-RandomIndex -Generator $rng -MaxExclusive ($i + 1)
            $tmp = $chars[$i]
            $chars[$i] = $chars[$j]
            $chars[$j] = $tmp
        }
        return (-join $chars)
    } finally {
        $rng.Dispose()
    }
}

function ConvertTo-PicoSecureString {
    param([Parameter(Mandatory = $true)][string]$PlainText)
    return (ConvertTo-SecureString -String $PlainText -AsPlainText -Force)
}

function New-SecurityIdentifier {
    param([Parameter(Mandatory = $true)][string]$Sid)
    return (New-Object -TypeName System.Security.Principal.SecurityIdentifier -ArgumentList $Sid)
}

function Get-LocalizedBuiltinGroupNameBySid {
    param([Parameter(Mandatory = $true)][string]$Sid)

    $sidObject = New-SecurityIdentifier -Sid $Sid
    $account = $sidObject.Translate([System.Security.Principal.NTAccount]).Value
    if ([string]::IsNullOrWhiteSpace($account)) {
        throw "No se pudo resolver grupo builtin por SID $Sid."
    }
    return (($account -split "\\")[-1])
}

function Test-LocalUserCmdletsAvailable {
    foreach ($name in @("Get-LocalUser", "New-LocalUser", "Set-LocalUser", "Enable-LocalUser")) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
            return $false
        }
    }
    return $true
}

function Test-LocalGroupCmdletsAvailable {
    foreach ($name in @("Get-LocalGroup", "Get-LocalGroupMember", "Add-LocalGroupMember", "Remove-LocalGroupMember")) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
            return $false
        }
    }
    return $true
}

function Get-LocalGroupObjectBySid {
    param([Parameter(Mandatory = $true)][string]$Sid)

    if (-not (Get-Command "Get-LocalGroup" -ErrorAction SilentlyContinue)) {
        return $null
    }
    try {
        return (Get-LocalGroup -SID (New-SecurityIdentifier -Sid $Sid) -ErrorAction Stop)
    } catch {
        Write-InstallLog "LOCAL_GROUP_BY_SID_FAILED sid=$Sid reason=$($_.Exception.Message)"
        return $null
    }
}

function Convert-LocalAccountNameToSid {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    try {
        $account = New-Object -TypeName System.Security.Principal.NTAccount -ArgumentList @($env:COMPUTERNAME, $AccountName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
    } catch {
        try {
            $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $AccountName)
            $sidBytes = [byte[]]$user.ObjectSid.Value
            $sidObject = New-Object -TypeName System.Security.Principal.SecurityIdentifier -ArgumentList @($sidBytes, 0)
            return $sidObject.Value
        } catch {
            throw "No se pudo resolver SID de la cuenta local $AccountName."
        }
    }
}

function Test-AdsiGroupMemberBySid {
    param(
        [Parameter(Mandatory = $true)][string]$GroupSid,
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$AccountSid
    )

    $groupName = Get-LocalizedBuiltinGroupNameBySid -Sid $GroupSid
    try {
        $group = [ADSI]("WinNT://{0}/{1},group" -f $env:COMPUTERNAME, $groupName)
        foreach ($member in @($group.psbase.Invoke("Members"))) {
            $memberName = [string]$member.GetType().InvokeMember("Name", "GetProperty", $null, $member, $null)
            if ($memberName -ieq $AccountName) {
                return $true
            }
            try {
                $memberSidBytes = [byte[]]$member.GetType().InvokeMember("objectSid", "GetProperty", $null, $member, $null)
                $memberSidObject = New-Object -TypeName System.Security.Principal.SecurityIdentifier -ArgumentList @($memberSidBytes, 0)
                $memberSid = $memberSidObject.Value
                if ($memberSid -eq $AccountSid) {
                    return $true
                }
            } catch {
            }
        }
    } catch {
        Write-InstallLog "ADSI_GROUP_MEMBER_CHECK_FAILED sid=$GroupSid account=$AccountName reason=$($_.Exception.Message)"
    }
    return $false
}

function Test-LocalAccountInGroupSid {
    param(
        [Parameter(Mandatory = $true)][string]$GroupSid,
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$AccountSid
    )

    if (Test-LocalGroupCmdletsAvailable) {
        $group = Get-LocalGroupObjectBySid -Sid $GroupSid
        if ($group) {
            try {
                foreach ($member in @(Get-LocalGroupMember -Group $group -ErrorAction Stop)) {
                    $memberSid = ""
                    if ($member.SID) { $memberSid = [string]$member.SID.Value }
                    if ($memberSid -eq $AccountSid) {
                        return $true
                    }
                }
                return $false
            } catch {
                Write-InstallLog "LOCAL_GROUP_MEMBER_CHECK_FAILED sid=$GroupSid account=$AccountName reason=$($_.Exception.Message)"
            }
        }
    }

    return (Test-AdsiGroupMemberBySid -GroupSid $GroupSid -AccountName $AccountName -AccountSid $AccountSid)
}

function Invoke-NetUserSafe {
    param(
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$Password,
        [switch]$Create
    )

    $netExe = Join-Path $env:SystemRoot "System32\net.exe"
    $stdout = Join-Path (Get-LogsDir) ("net-user-" + [Guid]::NewGuid().ToString("N") + ".out")
    $stderr = Join-Path (Get-LogsDir) ("net-user-" + [Guid]::NewGuid().ToString("N") + ".err")
    $args = if ($Create) {
        @("user", $AccountName, $Password, "/add", "/y")
    } else {
        @("user", $AccountName, $Password)
    }
    $safeAction = if ($Create) { "create" } else { "reset-password" }
    Write-InstallLog "RUN net.exe user $AccountName ***REDACTED*** action=$safeAction"
    try {
        & $netExe @args > $stdout 2> $stderr
        $exitCode = $LASTEXITCODE
        if (Test-Path -LiteralPath $stdout -PathType Leaf) {
            Add-Content -LiteralPath (Get-NativeLogPath "install-services.log") -Value (Protect-Text (Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue)) -Encoding UTF8
        }
        if (Test-Path -LiteralPath $stderr -PathType Leaf) {
            Add-Content -LiteralPath (Get-NativeLogPath "install-services.log") -Value (Protect-Text (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue)) -Encoding UTF8
        }
        Write-InstallLog "EXIT_CODE net.exe user action=$safeAction code=$exitCode"
        if ($exitCode -ne 0) {
            throw "net.exe user fallo con codigo $exitCode."
        }

        & $netExe user $AccountName /active:yes /expires:never /passwordchg:no > $stdout 2> $stderr
        $exitCode = $LASTEXITCODE
        Write-InstallLog "EXIT_CODE net.exe user flags code=$exitCode"
        if ($exitCode -ne 0) {
            throw "net.exe user flags fallo con codigo $exitCode."
        }
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-WmicPasswordNeverExpires {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $wmic = Join-Path $env:SystemRoot "System32\wbem\wmic.exe"
    if (-not (Test-Path -LiteralPath $wmic -PathType Leaf)) {
        Write-InstallLog "PICO_SERVICE_ACCOUNT_WMIC_PASSWORD_EXPIRES_SKIPPED name=$AccountName reason=wmic-missing"
        return $false
    }

    $stdout = Join-Path (Get-LogsDir) ("wmic-user-" + [Guid]::NewGuid().ToString("N") + ".out")
    $stderr = Join-Path (Get-LogsDir) ("wmic-user-" + [Guid]::NewGuid().ToString("N") + ".err")
    try {
        & $wmic UserAccount where "Name='$AccountName' and LocalAccount=True" set PasswordExpires=False > $stdout 2> $stderr
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            $tail = ""
            if (Test-Path -LiteralPath $stderr -PathType Leaf) {
                $tail = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
            }
            Write-InstallLog ("PICO_SERVICE_ACCOUNT_WMIC_PASSWORD_EXPIRES_FAILED name={0} code={1} {2}" -f $AccountName, $exitCode, $tail)
            return $false
        }
        Write-InstallLog "PICO_SERVICE_ACCOUNT_WMIC_PASSWORD_EXPIRES_OK name=$AccountName"
        return $true
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Set-PicoAdsiUserPasswordAndFlags {
    param(
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$Password,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $computer = [ADSI]("WinNT://{0}" -f $env:COMPUTERNAME)
    $user = $null
    try {
        $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $AccountName)
        $null = $user.Name
    } catch {
        $user = $computer.Create("user", $AccountName)
        $user.SetInfo()
    }

    $user.SetPassword($Password)
    $user.Put("Description", $Description)
    $flags = 0x0200 -bor 0x10000
    try {
        $currentFlags = [int]$user.UserFlags.Value
        $flags = ($currentFlags -bor 0x0200 -bor 0x10000) -band (-bnot 0x0002)
    } catch {
    }
    $user.Put("UserFlags", $flags)
    $user.SetInfo()
}

function Set-PicoAdsiPasswordNeverExpiresFlag {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    try {
        $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $AccountName)
        $null = $user.Name
        $currentFlags = 0
        try {
            $currentFlags = [int]$user.UserFlags.Value
        } catch {
            $currentFlags = 0x0200
        }
        $user.Put("UserFlags", ($currentFlags -bor 0x10000 -bor 0x0200))
        $user.SetInfo()
        Write-InstallLog "PICO_SERVICE_ACCOUNT_ADSI_PASSWORD_NEVER_EXPIRES_OK name=$AccountName"
        return $true
    } catch {
        Write-InstallLog "PICO_SERVICE_ACCOUNT_ADSI_PASSWORD_NEVER_EXPIRES_WARN name=$AccountName reason=$($_.Exception.Message)"
        return $false
    }
}

function Test-PicoServiceAccountPasswordNeverExpires {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    if (Test-LocalUserCmdletsAvailable) {
        try {
            $user = Get-LocalUser -Name $AccountName -ErrorAction Stop
            return ($null -eq $user.PasswordExpires)
        } catch {
            Write-InstallLog "PICO_SERVICE_ACCOUNT_PASSWORD_EXPIRES_LOCALACCOUNTS_WARN name=$AccountName reason=$($_.Exception.Message)"
        }
    }

    try {
        $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $AccountName)
        $null = $user.Name
        $flags = [int]$user.UserFlags.Value
        return (($flags -band 0x10000) -ne 0)
    } catch {
        Write-InstallLog "PICO_SERVICE_ACCOUNT_PASSWORD_EXPIRES_ADSI_WARN name=$AccountName reason=$($_.Exception.Message)"
    }

    return $false
}

function Get-PicoServiceAccountPasswordExpirySummary {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    if (Test-LocalUserCmdletsAvailable) {
        try {
            $user = Get-LocalUser -Name $AccountName -ErrorAction Stop
            $expires = if ($null -eq $user.PasswordExpires) { "never" } else { [string]$user.PasswordExpires }
            return "PasswordExpires=$expires PasswordNeverExpires=$(if ($null -eq $user.PasswordExpires) { 'true' } else { 'false' })"
        } catch {
        }
    }

    try {
        $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $AccountName)
        $null = $user.Name
        $flags = [int]$user.UserFlags.Value
        $never = (($flags -band 0x10000) -ne 0)
        return "PasswordNeverExpires=$never provider=ADSI"
    } catch {
    }

    return "PasswordNeverExpires=unknown"
}

function Ensure-PicoServiceAccountPasswordNeverExpires {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $configured = $false
    if (Test-LocalUserCmdletsAvailable) {
        try {
            Set-LocalUser -Name $AccountName -PasswordNeverExpires $true -ErrorAction Stop
            Write-InstallLog "PICO_SERVICE_ACCOUNT_PASSWORD_NEVER_EXPIRES_SET name=$AccountName provider=LocalAccounts"
            $configured = $true
        } catch {
            Write-InstallLog "PICO_SERVICE_ACCOUNT_PASSWORD_NEVER_EXPIRES_WARN name=$AccountName provider=LocalAccounts reason=$($_.Exception.Message)"
        }
    }

    if (Set-PicoAdsiPasswordNeverExpiresFlag -AccountName $AccountName) {
        $configured = $true
    }
    if (Invoke-WmicPasswordNeverExpires -AccountName $AccountName) {
        $configured = $true
    }

    if (-not $configured -or -not (Test-PicoServiceAccountPasswordNeverExpires -AccountName $AccountName)) {
        throw "No se pudo garantizar que la contrasena de $AccountName no expire. PostgreSQL no debe depender de una contrasena expirable."
    }

    Write-InstallLog ("PICO_SERVICE_ACCOUNT_PASSWORD_NEVER_EXPIRES_OK name={0} {1}" -f $AccountName, (Get-PicoServiceAccountPasswordExpirySummary -AccountName $AccountName))
}

function Invoke-LocalGroupMemberChange {
    param(
        [Parameter(Mandatory = $true)][string]$GroupSid,
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$Action
    )

    $localAccount = "{0}\{1}" -f $env:COMPUTERNAME, $AccountName
    $group = Get-LocalGroupObjectBySid -Sid $GroupSid
    if ($group -and (Test-LocalGroupCmdletsAvailable)) {
        try {
            if ($Action -eq "add") {
                Add-LocalGroupMember -Group $group -Member $localAccount -ErrorAction Stop
            } elseif ($Action -eq "remove") {
                Remove-LocalGroupMember -Group $group -Member $localAccount -ErrorAction Stop
            } else {
                throw "Accion de grupo no soportada: $Action"
            }
            Write-InstallLog "LOCAL_GROUP_MEMBER_CHANGE_OK sid=$GroupSid account=$AccountName action=$Action provider=LocalAccounts"
            return
        } catch {
            Write-InstallLog "LOCAL_GROUP_MEMBER_CHANGE_LOCALACCOUNTS_FAILED sid=$GroupSid account=$AccountName action=$Action reason=$($_.Exception.Message)"
        }
    }

    $groupName = Get-LocalizedBuiltinGroupNameBySid -Sid $GroupSid
    $netExe = Join-Path $env:SystemRoot "System32\net.exe"
    $netAction = if ($Action -eq "add") { "/add" } elseif ($Action -eq "remove") { "/delete" } else { throw "Accion de grupo no soportada: $Action" }
    Invoke-LoggedCommand `
        -FilePath $netExe `
        -ArgumentList @("localgroup", $groupName, $localAccount, $netAction) `
        -LogName "permissions.log"
    Write-InstallLog "LOCAL_GROUP_MEMBER_CHANGE_OK sid=$GroupSid account=$AccountName action=$Action provider=net"
}

function Ensure-PicoServiceAccountGroups {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $accountSid = Convert-LocalAccountNameToSid -AccountName $AccountName
    if (Test-LocalAccountInGroupSid -GroupSid $Script:BuiltinAdminGroupSid -AccountName $AccountName -AccountSid $accountSid) {
        Invoke-LocalGroupMemberChange -GroupSid $Script:BuiltinAdminGroupSid -AccountName $AccountName -Action "remove"
    }
    if (Test-LocalAccountInGroupSid -GroupSid $Script:BuiltinAdminGroupSid -AccountName $AccountName -AccountSid $accountSid) {
        throw "La cuenta $AccountName pertenece a un grupo administrativo. PostgreSQL no puede ejecutarse asi."
    }

    if (-not (Test-LocalAccountInGroupSid -GroupSid $Script:BuiltinStandardGroupSid -AccountName $AccountName -AccountSid $accountSid)) {
        try {
            Invoke-LocalGroupMemberChange -GroupSid $Script:BuiltinStandardGroupSid -AccountName $AccountName -Action "add"
        } catch {
            Write-InstallLog "PICO_SERVICE_ACCOUNT_STANDARD_GROUP_SKIPPED name=$AccountName sid=$Script:BuiltinStandardGroupSid reason=$($_.Exception.Message)"
        }
    }
}

function Ensure-PicoServiceAccount {
    $accountName = $Script:PicoServiceAccountName
    $description = "Servicio local Pico de Gallo"
    $password = New-SecureRandomPassword
    $securePassword = ConvertTo-PicoSecureString -PlainText $password
    $provider = "ADSI"

    if (Test-LocalUserCmdletsAvailable) {
        $provider = "LocalAccounts"
        try {
            $existing = Get-LocalUser -Name $accountName -ErrorAction SilentlyContinue
            if ($existing) {
                Set-LocalUser -Name $accountName -Password $securePassword -Description $description -ErrorAction Stop
                try { Set-LocalUser -Name $accountName -UserMayChangePassword $false -ErrorAction Stop } catch { Write-InstallLog "PICO_SERVICE_ACCOUNT_USER_MAY_CHANGE_PASSWORD_SKIPPED name=$accountName" }
                if (-not $existing.Enabled) {
                    Enable-LocalUser -Name $accountName -ErrorAction Stop
                }
                Write-InstallLog "PICO_SERVICE_ACCOUNT_PASSWORD_RESET name=$accountName provider=LocalAccounts"
            } else {
                $newParams = @{
                    Name = $accountName
                    Password = $securePassword
                    Description = $description
                    PasswordNeverExpires = $true
                }
                $newCommand = Get-Command New-LocalUser
                if ($newCommand.Parameters.ContainsKey("UserMayNotChangePassword")) {
                    $newParams["UserMayNotChangePassword"] = $true
                }
                if ($newCommand.Parameters.ContainsKey("AccountNeverExpires")) {
                    $newParams["AccountNeverExpires"] = $true
                }
                New-LocalUser @newParams -ErrorAction Stop | Out-Null
                Write-InstallLog "PICO_SERVICE_ACCOUNT_CREATED name=$accountName provider=LocalAccounts"
            }
        } catch {
            Write-InstallLog "PICO_SERVICE_ACCOUNT_LOCALACCOUNTS_FAILED name=$accountName reason=$($_.Exception.Message)"
            $provider = "ADSI"
            try {
                Set-PicoAdsiUserPasswordAndFlags -AccountName $accountName -Password $password -Description $description
                Write-InstallLog "PICO_SERVICE_ACCOUNT_READY_ADSI name=$accountName"
            } catch {
                Write-InstallLog "PICO_SERVICE_ACCOUNT_ADSI_WARN name=$accountName reason=$($_.Exception.Message)"
                $provider = "net"
                $exists = $false
                try {
                    $null = Convert-LocalAccountNameToSid -AccountName $accountName
                    $exists = $true
                } catch {
                }
                Invoke-NetUserSafe -AccountName $accountName -Password $password -Create:([bool](-not $exists))
                Write-InstallLog "PICO_SERVICE_ACCOUNT_READY_NET name=$accountName"
            }
        }
    } else {
        try {
            Set-PicoAdsiUserPasswordAndFlags -AccountName $accountName -Password $password -Description $description
            Write-InstallLog "PICO_SERVICE_ACCOUNT_READY_ADSI name=$accountName"
        } catch {
            Write-InstallLog "PICO_SERVICE_ACCOUNT_ADSI_WARN name=$accountName reason=$($_.Exception.Message)"
            $provider = "net"
            $exists = $false
            try {
                $null = Convert-LocalAccountNameToSid -AccountName $accountName
                $exists = $true
            } catch {
            }
            Invoke-NetUserSafe -AccountName $accountName -Password $password -Create:([bool](-not $exists))
            Write-InstallLog "PICO_SERVICE_ACCOUNT_READY_NET name=$accountName"
        }
    }

    Ensure-PicoServiceAccountPasswordNeverExpires -AccountName $accountName
    Ensure-PicoServiceAccountGroups -AccountName $accountName
    $accountSid = Convert-LocalAccountNameToSid -AccountName $accountName
    $credential = [System.Management.Automation.PSCredential]::new(".\$accountName", $securePassword)
    Write-InstallLog ("PICO_SERVICE_ACCOUNT_READY name={0} sid={1} provider={2} non_admin=true {3}" -f $accountName, $accountSid, $provider, (Get-PicoServiceAccountPasswordExpirySummary -AccountName $accountName))
    return [pscustomobject]@{
        Username = $accountName
        Domain = "."
        LocalAccount = ("{0}\{1}" -f $env:COMPUTERNAME, $accountName)
        Sid = $accountSid
        PlainPassword = $password
        Credential = $credential
    }
}

function Invoke-IcaclsGrant {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Account,
        [Parameter(Mandatory = $true)][string]$Rights
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        New-DirectorySafe $Path
    }

    $icacls = Join-Path $env:SystemRoot "System32\icacls.exe"
    Invoke-LoggedCommand `
        -FilePath $icacls `
        -ArgumentList @($Path, "/grant", "$($Account):(OI)(CI)$Rights", "/T", "/C") `
        -LogName "permissions.log"
    Write-InstallLog -LogName "permissions.log" -Message "ACL_GRANTED path=$Path account=$Account rights=$Rights"
}

function Grant-PicoServiceAccountPermissions {
    param([Parameter(Mandatory = $true)]$Account)

    $accountName = [string]$Account.LocalAccount

    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramDataDir "postgres") -Account $accountName -Rights "F"
    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramDataDir "logs") -Account $accountName -Rights "M"
    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramFilesDir "postgres") -Account $accountName -Rights "RX"
    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramFilesDir "services") -Account $accountName -Rights "RX"
}

function ConvertTo-StartProcessArgumentString {
    param([string[]]$ArgumentList = @())

    $escaped = foreach ($arg in $ArgumentList) {
        $text = [string]$arg
        if ($text -match '[\s"]') {
            '"' + $text.Replace('"', '\"') + '"'
        } else {
            $text
        }
    }
    return ($escaped -join " ")
}

function ConvertTo-PowerShellSingleQuotedString {
    param([string]$Text)

    return "'" + $Text.Replace("'", "''") + "'"
}

function Invoke-AsPicoServiceAccount {
    param(
        [Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][string]$LogName,
        [string]$WorkingDirectory,
        [string]$StdoutPath,
        [string]$StderrPath,
        [switch]$NoWait,
        [switch]$ReturnStdout
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "No existe ejecutable requerido: $FilePath"
    }

    $createdDefaultStdout = $false
    $createdDefaultStderr = $false
    if ([string]::IsNullOrWhiteSpace($StdoutPath)) {
        $StdoutPath = Join-Path (Get-LogsDir) ("{0}.stdout.tmp" -f ([Guid]::NewGuid().ToString("N")))
        $createdDefaultStdout = $true
    }
    if ([string]::IsNullOrWhiteSpace($StderrPath)) {
        $StderrPath = Join-Path (Get-LogsDir) ("{0}.stderr.tmp" -f ([Guid]::NewGuid().ToString("N")))
        $createdDefaultStderr = $true
    }

    $argumentString = ConvertTo-StartProcessArgumentString -ArgumentList $ArgumentList
    $safeCommand = Format-CommandForLog -FilePath $FilePath -ArgumentList $ArgumentList
    Write-InstallLog -LogName $LogName -Message ("RUN_AS_BEGIN account={0} command={1} stdout={2} stderr={3} noWait={4}" -f $Script:PicoServiceAccountName, $safeCommand, $StdoutPath, $StderrPath, [bool]$NoWait)

    if ($NoWait) {
        $startParams = @{
            FilePath = $FilePath
            ArgumentList = $argumentString
            Credential = $Credential
            RedirectStandardOutput = $StdoutPath
            RedirectStandardError = $StderrPath
            WindowStyle = "Hidden"
            PassThru = $true
        }
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            $startParams["WorkingDirectory"] = $WorkingDirectory
        }

        $process = Start-Process @startParams
        Write-InstallLog -LogName $LogName -Message ("RUN_AS_STARTED account={0} pid={1}" -f $Script:PicoServiceAccountName, $process.Id)
        return $process
    }

    $runAsDir = Join-Path (Get-LogsDir) "runas"
    New-DirectorySafe $runAsDir
    $runId = [Guid]::NewGuid().ToString("N")
    $wrapperPath = Join-Path $runAsDir "runas-$runId.ps1"
    $configPath = Join-Path $runAsDir "runas-$runId.json"
    $exitCodePath = Join-Path $runAsDir "runas-$runId.exitcode"
    $donePath = Join-Path $runAsDir "runas-$runId.done"
    $wrapperLogPath = Join-Path $runAsDir "runas-$runId.wrapper.log"
    $powershellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path -LiteralPath $powershellExe -PathType Leaf)) {
        $powershellExe = "powershell.exe"
    }

    $runConfig = [pscustomobject]@{
        FilePath = $FilePath
        ArgumentList = @($ArgumentList)
        WorkingDirectory = $WorkingDirectory
        StdoutPath = $StdoutPath
        StderrPath = $StderrPath
    }
    $runConfig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8

    $wrapper = @"
`$ErrorActionPreference = "Stop"
`$configPath = $(ConvertTo-PowerShellSingleQuotedString -Text $configPath)
`$exitCodePath = $(ConvertTo-PowerShellSingleQuotedString -Text $exitCodePath)
`$donePath = $(ConvertTo-PowerShellSingleQuotedString -Text $donePath)
`$wrapperLogPath = $(ConvertTo-PowerShellSingleQuotedString -Text $wrapperLogPath)
`$stdoutPath = ""
`$stderrPath = ""
`$code = 1
try {
    `$config = Get-Content -LiteralPath `$configPath -Raw | ConvertFrom-Json
    `$stdoutPath = [string]`$config.StdoutPath
    `$stderrPath = [string]`$config.StderrPath
    foreach (`$path in @(`$stdoutPath, `$stderrPath, `$wrapperLogPath, `$exitCodePath, `$donePath)) {
        if (-not [string]::IsNullOrWhiteSpace(`$path)) {
            `$dir = Split-Path -Path `$path -Parent
            if (-not [string]::IsNullOrWhiteSpace(`$dir) -and -not (Test-Path -LiteralPath `$dir)) {
                New-Item -ItemType Directory -Path `$dir -Force | Out-Null
            }
        }
    }
    `$argsList = @()
    if (`$null -ne `$config.ArgumentList) {
        foreach (`$arg in @(`$config.ArgumentList)) {
            `$argsList += [string]`$arg
        }
    }
    if (-not [string]::IsNullOrWhiteSpace([string]`$config.WorkingDirectory)) {
        Set-Location -LiteralPath ([string]`$config.WorkingDirectory)
    }
    & ([string]`$config.FilePath) @argsList > `$stdoutPath 2> `$stderrPath
    `$code = `$LASTEXITCODE
    if (`$null -eq `$code) {
        `$code = 0
    }
} catch {
    `$code = 1
    try {
        Add-Content -LiteralPath `$wrapperLogPath -Value ("WRAPPER_EXCEPTION " + `$_.Exception.GetType().FullName + " " + `$_.Exception.Message) -Encoding UTF8
    } catch {
    }
    if (-not [string]::IsNullOrWhiteSpace(`$stderrPath)) {
        try {
            Add-Content -LiteralPath `$stderrPath -Value ("WRAPPER_EXCEPTION " + `$_.Exception.Message) -Encoding UTF8
        } catch {
        }
    }
}
try {
    Set-Content -LiteralPath `$exitCodePath -Value ([string][int]`$code) -Encoding ASCII
} finally {
    Set-Content -LiteralPath `$donePath -Value "done" -Encoding ASCII
}
exit ([int]`$code)
"@
    Set-Content -LiteralPath $wrapperPath -Value $wrapper -Encoding UTF8

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $startParams = @{
        FilePath = $powershellExe
        ArgumentList = (ConvertTo-StartProcessArgumentString -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $wrapperPath))
        Credential = $Credential
        WindowStyle = "Hidden"
        PassThru = $true
    }
    Write-InstallLog -LogName $LogName -Message ("RUN_AS_WRAPPER_BEGIN account={0} wrapper={1} exitcode={2}" -f $Script:PicoServiceAccountName, $wrapperPath, $exitCodePath)
    $wrapperProcess = Start-Process @startParams
    $wrapperProcess.WaitForExit()
    for ($i = 0; $i -lt 50; $i++) {
        if ((Test-Path -LiteralPath $donePath -PathType Leaf) -and (Test-Path -LiteralPath $exitCodePath -PathType Leaf)) {
            break
        }
        Start-Sleep -Milliseconds 200
    }
    $stopwatch.Stop()

    $stdoutText = ""
    $stderrText = ""
    if (Test-Path -LiteralPath $StdoutPath -PathType Leaf) {
        $stdoutText = Get-Content -LiteralPath $StdoutPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stdoutText)) {
            Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value (Protect-Text $stdoutText) -Encoding UTF8
        }
    }
    if (Test-Path -LiteralPath $StderrPath -PathType Leaf) {
        $stderrText = Get-Content -LiteralPath $StderrPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
            Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value (Protect-Text $stderrText) -Encoding UTF8
        }
    }

    if (-not (Test-Path -LiteralPath $exitCodePath -PathType Leaf)) {
        $wrapperTail = Get-LogTailText -Path $wrapperLogPath -Lines 80
        Write-InstallLog -LogName $LogName -Message ("RUN_AS_ERROR account={0} reason=missing-exitcode wrapper={1} stdout={2} stderr={3} durationMs={4}" -f $Script:PicoServiceAccountName, $wrapperPath, $StdoutPath, $StderrPath, $stopwatch.ElapsedMilliseconds)
        if (-not [string]::IsNullOrWhiteSpace($wrapperTail)) {
            Write-InstallLog -LogName $LogName -Message ("RUN_AS_WRAPPER_TAIL`n" + $wrapperTail)
        }
        throw "No se pudo capturar exit code de proceso ejecutado como $Script:PicoServiceAccountName. Revise $(Get-NativeLogPath $LogName) y $wrapperLogPath"
    }

    $exitText = (Get-Content -LiteralPath $exitCodePath -Raw -ErrorAction Stop).Trim()
    $exitCode = 0
    if (-not [int]::TryParse($exitText, [ref]$exitCode)) {
        Write-InstallLog -LogName $LogName -Message ("RUN_AS_ERROR account={0} reason=invalid-exitcode value={1} wrapper={2}" -f $Script:PicoServiceAccountName, $exitText, $wrapperPath)
        throw "Exit code invalido capturado para proceso ejecutado como $Script:PicoServiceAccountName: $exitText"
    }

    Write-InstallLog -LogName $LogName -Message ("RUN_AS_DONE account={0} exitcode={1} stdout={2} stderr={3} durationMs={4}" -f $Script:PicoServiceAccountName, $exitCode, $StdoutPath, $StderrPath, $stopwatch.ElapsedMilliseconds)
    Write-InstallLog -LogName $LogName -Message ("EXIT_CODE_SENTINEL " + $exitCode)
    if ($exitCode -ne 0) {
        $stdoutTail = Get-LogTailText -Path $StdoutPath -Lines 80
        $stderrTail = Get-LogTailText -Path $StderrPath -Lines 80
        Write-InstallLog -LogName $LogName -Message ("RUN_AS_ERROR account={0} exitcode={1} stdout={2} stderr={3}" -f $Script:PicoServiceAccountName, $exitCode, $StdoutPath, $StderrPath)
        if (-not [string]::IsNullOrWhiteSpace($stdoutTail)) {
            Write-InstallLog -LogName $LogName -Message ("RUN_AS_STDOUT_TAIL`n" + $stdoutTail)
        }
        if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
            Write-InstallLog -LogName $LogName -Message ("RUN_AS_STDERR_TAIL`n" + $stderrTail)
        }
        throw "Comando como $Script:PicoServiceAccountName fallo con codigo $exitCode. Revise $(Get-NativeLogPath $LogName)"
    }

    Remove-Item -LiteralPath $wrapperPath, $configPath, $exitCodePath, $donePath, $wrapperLogPath -Force -ErrorAction SilentlyContinue
    if ($createdDefaultStdout) {
        Remove-Item -LiteralPath $StdoutPath -Force -ErrorAction SilentlyContinue
    }
    if ($createdDefaultStderr) {
        Remove-Item -LiteralPath $StderrPath -Force -ErrorAction SilentlyContinue
    }
    if ($ReturnStdout) {
        return $stdoutText
    }
}

function Escape-XmlText {
    param([string]$Text)
    return [System.Security.SecurityElement]::Escape($Text)
}

function New-WinSWServiceAccountXml {
    param([string]$Password)

    $lines = @(
        "  <serviceaccount>",
        "    <domain>.</domain>",
        ("    <user>{0}</user>" -f (Escape-XmlText $Script:PicoServiceAccountName))
    )
    if (-not [string]::IsNullOrEmpty($Password)) {
        $lines += ("    <password>{0}</password>" -f (Escape-XmlText $Password))
    }
    $lines += "    <allowservicelogon>true</allowservicelogon>"
    $lines += "  </serviceaccount>"
    return ($lines -join "`r`n")
}

function Assert-SecretAbsentFromFiles {
    param(
        [Parameter(Mandatory = $true)][string]$Secret,
        [Parameter(Mandatory = $true)][string[]]$Paths
    )

    if ([string]::IsNullOrEmpty($Secret)) {
        return
    }

    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            continue
        }
        $text = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
        if ($text -and $text.Contains($Secret)) {
            Set-Content -LiteralPath $path -Value ($text.Replace($Secret, "***REDACTED***")) -Encoding UTF8
            throw "La contrasena de $Script:PicoServiceAccountName quedo persistida en $path. El valor fue redactado y la instalacion se detuvo."
        }
    }
}

function Get-ServiceLogonNativeApi {
    if (-not ("PicoDeGallo.Native.ServiceLogon" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace PicoDeGallo.Native {
    public static class ServiceLogon {
        public const UInt32 SC_MANAGER_CONNECT = 0x0001;
        public const UInt32 SERVICE_QUERY_CONFIG = 0x0001;
        public const UInt32 SERVICE_CHANGE_CONFIG = 0x0002;
        public const UInt32 SERVICE_NO_CHANGE = 0xFFFFFFFF;

        [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        public static extern IntPtr OpenSCManager(string machineName, string databaseName, UInt32 desiredAccess);

        [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        public static extern IntPtr OpenService(IntPtr scmHandle, string serviceName, UInt32 desiredAccess);

        [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        public static extern bool ChangeServiceConfig(
            IntPtr serviceHandle,
            UInt32 serviceType,
            UInt32 startType,
            UInt32 errorControl,
            string binaryPathName,
            string loadOrderGroup,
            IntPtr tagId,
            string dependencies,
            string serviceStartName,
            string password,
            string displayName);

        [DllImport("advapi32.dll", SetLastError=true)]
        public static extern bool CloseServiceHandle(IntPtr handle);

        public static Win32Exception LastError() {
            return new Win32Exception(Marshal.GetLastWin32Error());
        }
    }
}
"@
    }
    return [PicoDeGallo.Native.ServiceLogon]
}

function Get-PicoServiceAccountLogonName {
    $computer = [string]$env:COMPUTERNAME
    if (-not [string]::IsNullOrWhiteSpace($computer)) {
        return ("{0}\{1}" -f $computer, $Script:PicoServiceAccountName)
    }
    return (".\{0}" -f $Script:PicoServiceAccountName)
}

function Test-PostgresServiceAccountStartName {
    param([string]$StartName)

    if ([string]::IsNullOrWhiteSpace($StartName) -or $StartName -eq "unknown") {
        return $false
    }

    $trimmed = $StartName.Trim()
    $blocked = @(
        "LocalSystem",
        "NT AUTHORITY\SYSTEM",
        "LocalService",
        "NT AUTHORITY\LocalService",
        "NetworkService",
        "NT AUTHORITY\NetworkService",
        "Administrador",
        "Administrator",
        "CAJA"
    )
    foreach ($name in $blocked) {
        if ($trimmed -ieq $name) {
            return $false
        }
    }

    if ($trimmed -ieq (Get-PicoServiceAccountLogonName)) {
        return $true
    }

    $computer = [string]$env:COMPUTERNAME
    if (-not [string]::IsNullOrWhiteSpace($computer) -and $trimmed -ieq ("{0}\{1}" -f $computer, $Script:PicoServiceAccountName)) {
        return $true
    }

    return $false
}

function Set-WindowsServiceLogonAccountSafe {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$Password,
        [string]$LogName = "service-install.log"
    )

    if ([string]::IsNullOrEmpty($Password)) {
        throw "No se puede configurar cuenta de servicio $ServiceId sin password en memoria."
    }

    Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_BEGIN service=$ServiceId account=$AccountName"
    $cimChanged = $false
    try {
        $escaped = $ServiceId.Replace("'", "''")
        $service = Get-CimInstance Win32_Service -Filter "Name='$escaped'" -ErrorAction Stop
        if (-not $service) {
            throw "Servicio no encontrado: $ServiceId"
        }
        $result = Invoke-CimMethod `
            -InputObject $service `
            -MethodName Change `
            -Arguments @{ StartName = $AccountName; StartPassword = $Password } `
            -ErrorAction Stop
        $returnValue = [int]$result.ReturnValue
        if ($returnValue -ne 0) {
            throw "Win32_Service.Change ReturnValue=$returnValue"
        }
        $cimChanged = $true
        Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_CIM_OK service=$ServiceId account=$AccountName"
    } catch {
        Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_CIM_WARN service=$ServiceId account=$AccountName message=$($_.Exception.Message)"
    }

    if ($cimChanged) {
        $startName = Get-ServiceStartNameSafe -Name $ServiceId
        Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_OK service=$ServiceId startName=$startName method=cim"
        return
    }

    $api = Get-ServiceLogonNativeApi
    $scm = [IntPtr]::Zero
    $svc = [IntPtr]::Zero
    $nativeChanged = $false
    try {
        $machineName = [string]$env:COMPUTERNAME
        if ([string]::IsNullOrWhiteSpace($machineName)) {
            $machineName = $null
        }
        $scm = $api::OpenSCManager($machineName, "ServicesActive", [uint32]$api::SC_MANAGER_CONNECT)
        if ($scm -eq [IntPtr]::Zero) {
            throw $api::LastError()
        }

        $access = [uint32]($api::SERVICE_CHANGE_CONFIG -bor $api::SERVICE_QUERY_CONFIG)
        $svc = $api::OpenService($scm, $ServiceId, $access)
        if ($svc -eq [IntPtr]::Zero) {
            throw $api::LastError()
        }

        $noChange = [uint32]$api::SERVICE_NO_CHANGE
        $ok = $api::ChangeServiceConfig(
            $svc,
            $noChange,
            $noChange,
            $noChange,
            $null,
            $null,
            [IntPtr]::Zero,
            $null,
            $AccountName,
            $Password,
            $null)
        if (-not $ok) {
            throw $api::LastError()
        }
        $nativeChanged = $true
        Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_NATIVE_OK service=$ServiceId account=$AccountName"
    } catch {
        Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_NATIVE_WARN service=$ServiceId account=$AccountName message=$($_.Exception.Message)"
    } finally {
        if ($svc -ne [IntPtr]::Zero) {
            [void]$api::CloseServiceHandle($svc)
        }
        if ($scm -ne [IntPtr]::Zero) {
            [void]$api::CloseServiceHandle($scm)
        }
    }

    if ($nativeChanged) {
        $startName = Get-ServiceStartNameSafe -Name $ServiceId
        Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_OK service=$ServiceId startName=$startName method=native"
        return
    }

    $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
    Invoke-LoggedSecretCommand `
        -FilePath $scExe `
        -ArgumentList @("config", $ServiceId, "obj=", $AccountName, "password=", $Password) `
        -SafeArgumentList @("config", $ServiceId, "obj=", $AccountName, "password=", "***REDACTED***") `
        -SecretValues @($Password) `
        -LogName $LogName
    $startName = Get-ServiceStartNameSafe -Name $ServiceId
    Write-InstallLog -LogName $LogName -Message "SERVICE_ACCOUNT_FIX_OK service=$ServiceId startName=$startName method=sc.exe"
}

function Assert-PostgresServiceAccount {
    $startName = Get-ServiceStartNameSafe -Name "PicoDeGallo-PostgreSQL"
    $ok = Test-PostgresServiceAccountStartName -StartName $startName
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_SERVICE_START_NAME actual=$startName expected=$Script:PicoServiceAccountName ok=$ok"
    Write-InstallLog -LogName "service-install.log" -Message "POSTGRES_SERVICE_START_NAME actual=$startName expected=$Script:PicoServiceAccountName ok=$ok"
    if (-not $ok) {
        throw "PicoDeGallo-PostgreSQL quedo configurado como $startName; debe ejecutar como $(Get-PicoServiceAccountLogonName)."
    }
}

function Install-WinSWServiceWithAccount {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Tokens,
        [Parameter(Mandatory = $true)][string]$Template,
        [Parameter(Mandatory = $true)][string]$TargetXml,
        [Parameter(Mandatory = $true)][string]$TargetExe,
        [Parameter(Mandatory = $true)][string]$WinSWSource,
        [Parameter(Mandatory = $true)]$PicoServiceAccount,
        [Parameter(Mandatory = $true)][string]$ServiceId
    )

    $password = [string]$PicoServiceAccount.PlainPassword
    $installTokens = $Tokens.Clone()
    $installTokens["PICO_SERVICE_ACCOUNT_XML"] = New-WinSWServiceAccountXml -Password $password
    $finalTokens = $Tokens.Clone()
    $finalTokens["PICO_SERVICE_ACCOUNT_XML"] = New-WinSWServiceAccountXml

    try {
        Render-Template -Source $Template -Destination $TargetXml -Tokens $installTokens
        if ((Get-Content -LiteralPath $TargetXml -Raw).Contains("{{")) {
            throw "XML WinSW renderizado contiene placeholders sin resolver: $TargetXml"
        }
        Copy-Item -LiteralPath $WinSWSource -Destination $TargetExe -Force
        Invoke-WinSWCommand -ServiceId $ServiceId -Command "install"
        $startName = Get-ServiceStartNameSafe -Name $ServiceId
        if (-not (Test-PostgresServiceAccountStartName -StartName $startName)) {
            Write-InstallLog -LogName "service-install.log" -Message "SERVICE_ACCOUNT_FIX_REQUIRED service=$ServiceId actual=$startName expected=$(Get-PicoServiceAccountLogonName)"
            Set-WindowsServiceLogonAccountSafe `
                -ServiceId $ServiceId `
                -AccountName (Get-PicoServiceAccountLogonName) `
                -Password $password
        }
    } finally {
        Render-Template -Source $Template -Destination $TargetXml -Tokens $finalTokens
        Assert-SecretAbsentFromFiles -Secret $password -Paths @($TargetXml)
    }

    Assert-SecretAbsentFromFiles -Secret $password -Paths @(
        (Get-NativeLogPath "service-install.log"),
        (Get-NativeLogPath "install-services.log"),
        (Get-NativeLogPath "postgres-service.log"),
        (Get-NativeLogPath "install-services-transcript.log")
    )
    Wait-ServiceStatus -ServiceId $ServiceId -DesiredStatus "Stopped" -TimeoutSeconds 30
    Assert-PostgresServiceAccount
}

function Stop-ExistingServicesForLogArchive {
    $serviceIds = @($Script:Services)
    [array]::Reverse($serviceIds)

    foreach ($serviceId in $serviceIds) {
        $service = Get-ServiceSafe $serviceId
        if ($service -and $service.Status -eq "Running") {
            Write-SafeHost "Deteniendo servicio existente antes de archivar logs: $serviceId"
            Stop-Service -Name $serviceId -ErrorAction Stop
            $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Stopped, [TimeSpan]::FromSeconds(90))
        }
    }
}

function Archive-ExistingNativeLogs {
    $logsDir = Get-LogsDir
    if (-not (Test-Path -LiteralPath $logsDir -PathType Container)) {
        return
    }

    $items = @(Get-ChildItem -LiteralPath $logsDir -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "archive" })
    if ($items.Count -eq 0) {
        return
    }

    $archiveRoot = Join-Path $logsDir "archive"
    New-DirectorySafe $archiveRoot
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $archiveDir = Join-Path $archiveRoot $stamp
    $suffix = 0
    while (Test-Path -LiteralPath $archiveDir) {
        $suffix++
        $archiveDir = Join-Path $archiveRoot ("{0}-{1}" -f $stamp, $suffix)
    }
    New-DirectorySafe $archiveDir

    foreach ($item in $items) {
        Move-Item -LiteralPath $item.FullName -Destination $archiveDir -Force -ErrorAction Stop
    }

    Write-SafeHost "Logs anteriores archivados en $archiveDir"
}

function Get-InstalledVersionForInstallLog {
    $versionPath = Join-Path $Script:ProgramFilesDir "version.json"
    if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
        return "missing"
    }
    try {
        $json = Get-Content -LiteralPath $versionPath -Raw -ErrorAction Stop | ConvertFrom-Json
        if ($json.version) {
            return [string]$json.version
        }
    } catch {
        return "error"
    }
    return "unknown"
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

function Write-LogTail {
    param(
        [Parameter(Mandatory = $true)][string]$LogName,
        [int]$Lines = 80,
        [string]$TargetLogName = "service-install.log"
    )

    $path = Join-Path (Get-LogsDir) $LogName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Write-InstallLog -LogName $TargetLogName -Message "LOG_TAIL_MISSING $LogName"
        return
    }

    Write-InstallLog -LogName $TargetLogName -Message "LOG_TAIL_BEGIN $LogName"
    $tail = Get-Content -LiteralPath $path -Tail $Lines -ErrorAction SilentlyContinue
    if ($tail) {
        Add-Content -LiteralPath (Get-NativeLogPath $TargetLogName) -Value (Protect-Text (($tail | ForEach-Object { [string]$_ }) -join "`n")) -Encoding UTF8
    }
    Write-InstallLog -LogName $TargetLogName -Message "LOG_TAIL_END $LogName"
}

function Write-ServiceFailureDiagnostics {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [int]$Port = 0,
        [string]$HostName = "127.0.0.1"
    )

    $service = Get-ServiceSafe $ServiceId
    $status = if ($service) { [string]$service.Status } else { "not-installed" }
    Write-InstallLog -LogName "service-install.log" -Message "SERVICE_FAILURE $ServiceId status=$status"
    Write-InstallLog -LogName "install-services.log" -Message "SERVICE_FAILURE $ServiceId status=$status"
    if ($Port -gt 0) {
        $portStatus = if (Test-TcpPort -HostName $HostName -Port $Port) { "listening" } else { "closed" }
        Write-InstallLog -LogName "healthcheck.log" -Message "TCP_STATUS $HostName`:$Port $portStatus"
    }

    foreach ($logName in @(
        "$ServiceId.wrapper.log",
        "$ServiceId.err.log",
        "$ServiceId.out.log",
        "postgres-foreground-test.err.log",
        "postgres-foreground-test.out.log",
        "postgres-version.log",
        "initdb-version.log",
        "psql-version.log",
        "postgres-init.log",
        "postgres-service.log"
    )) {
        Write-LogTail -LogName $logName -TargetLogName "service-install.log"
    }

    if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
        $combinedTail = ""
        foreach ($logName in @("$ServiceId.wrapper.log", "$ServiceId.err.log", "postgres-service.log")) {
            $path = Join-Path (Get-LogsDir) $logName
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $combinedTail += "`n" + ((Get-Content -LiteralPath $path -Tail 120 -ErrorAction SilentlyContinue | ForEach-Object { [string]$_ }) -join "`n")
            }
        }
        if ($combinedTail -match "Execution of PostgreSQL by a user with administrative permissions is not permitted" -or
            $combinedTail -match "No se permite ejecuci.n del servidor PostgreSQL por un usuario con privilegios administrativos") {
            Write-InstallLog -LogName "service-install.log" -Message "POSTGRES_PRIVILEGED_SERVICE_ACCOUNT_ERROR El servicio PostgreSQL fue instalado con una cuenta privilegiada; debe corregirse la cuenta de servicio, no la configuracion PostgreSQL."
        }
    }
}

function Wait-TcpPort {
    param(
        [string]$HostName = "127.0.0.1",
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 60,
        [string]$ServiceId
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-TcpPort -HostName $HostName -Port $Port) {
            Write-InstallLog -LogName "healthcheck.log" -Message "TCP_OK $HostName`:$Port"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-InstallLog -LogName "healthcheck.log" -Message "TCP_FAILED $HostName`:$Port"
    if (-not [string]::IsNullOrWhiteSpace($ServiceId)) {
        Write-ServiceFailureDiagnostics -ServiceId $ServiceId -HostName $HostName -Port $Port
    }
    throw "Puerto TCP no quedo escuchando: $HostName`:$Port"
}

function Wait-ServiceStatus {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [Parameter(Mandatory = $true)][string]$DesiredStatus,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $service = Get-ServiceSafe $ServiceId
        if ($service -and ([string]$service.Status) -eq $DesiredStatus) {
            Write-InstallLog "SERVICE_STATUS $ServiceId $DesiredStatus"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    $current = Get-ServiceSafe $ServiceId
    $status = if ($current) { [string]$current.Status } else { "not-installed" }
    Write-ServiceFailureDiagnostics -ServiceId $ServiceId
    throw "Servicio $ServiceId no llego a estado $DesiredStatus. Estado actual: $status"
}

function Wait-ServiceRemoved {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Get-ServiceSafe $ServiceId)) {
            Write-InstallLog -LogName "service-install.log" -Message "SERVICE_REMOVED $ServiceId"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw "Servicio $ServiceId no fue eliminado completamente despues de uninstall."
}

function Start-WinSWService {
    param([Parameter(Mandatory = $true)][string]$ServiceId)

    $service = Get-ServiceSafe $ServiceId
    if (-not $service) {
        throw "Servicio requerido no instalado: $ServiceId"
    }
    if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
        Assert-PostgresServiceAccount
    }
    if ($service.Status -eq "Running") {
        Write-InstallLog "SERVICE_ALREADY_RUNNING $ServiceId"
        if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
            Write-InstallLog -LogName "postgres-service.log" -Message "SERVICE_ALREADY_RUNNING $ServiceId"
        }
        return
    }

    try {
        Invoke-WinSWCommand -ServiceId $ServiceId -Command "start"
    } catch {
        $service = Get-ServiceSafe $ServiceId
        if (-not $service -or $service.Status -ne "Running") {
            Write-ServiceFailureDiagnostics -ServiceId $ServiceId
            throw
        }
    }

    Wait-ServiceStatus -ServiceId $ServiceId -DesiredStatus "Running" -TimeoutSeconds 90
    if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
        Write-InstallLog -LogName "postgres-service.log" -Message "SERVICE_RUNNING $ServiceId"
    }
    Write-SafeHost "Servicio iniciado: $ServiceId"
}

function Assert-AllServicesInstalled {
    foreach ($serviceId in $Script:Services) {
        if (-not (Get-ServiceSafe $serviceId)) {
            throw "Servicio requerido no instalado: $serviceId"
        }
    }
}

function Assert-AllServicesRunning {
    foreach ($serviceId in $Script:Services) {
        Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Running" -TimeoutSeconds 30
    }
}

function Assert-ServiceTemplatesAvailable {
    $templateDir = Join-Path (Join-Path $Script:ProgramFilesDir "services") "templates"
    if (-not (Test-Path -LiteralPath $templateDir -PathType Container)) {
        throw "No existen templates de servicios en $templateDir"
    }
    foreach ($serviceId in $Script:Services) {
        $template = Join-Path $templateDir "$serviceId.xml"
        if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
            throw "Falta template WinSW para $serviceId en $template"
        }
    }
}

function Assert-WinSWServiceFiles {
    param([Parameter(Mandatory = $true)][string]$ServiceId)

    $serviceDir = Join-Path $Script:ProgramFilesDir "services"
    $targetXml = Join-Path $serviceDir "$ServiceId.xml"
    $targetExe = Join-Path $serviceDir "$ServiceId.exe"
    if (-not (Test-Path -LiteralPath $targetExe -PathType Leaf)) {
        throw ("No se genero wrapper WinSW final para {0}: {1}" -f $ServiceId, $targetExe)
    }
    if (-not (Test-Path -LiteralPath $targetXml -PathType Leaf)) {
        throw ("No se genero XML WinSW final para {0}: {1}" -f $ServiceId, $targetXml)
    }
    $xmlText = Get-Content -LiteralPath $targetXml -Raw
    if ($xmlText.Contains("{{")) {
        throw "XML WinSW final contiene placeholders sin resolver: $targetXml"
    }
}

function Assert-WinSWServiceFilesForAll {
    param([string[]]$ServiceIds = $Script:Services)

    foreach ($serviceId in $ServiceIds) {
        Assert-WinSWServiceFiles -ServiceId $serviceId
    }
}

function Install-WinSWServices {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Tokens,
        [string[]]$ServiceIds = $Script:Services,
        $PicoServiceAccount
    )

    $serviceDir = Join-Path $Script:ProgramFilesDir "services"
    $templateDir = Join-Path $serviceDir "templates"
    $winswSource = Join-Path $serviceDir "winsw.exe"

    if (-not (Test-Path -LiteralPath $winswSource -PathType Leaf)) {
        throw "No existe WinSW en $winswSource"
    }
    if (-not (Test-Path -LiteralPath $templateDir -PathType Container)) {
        throw "No existen templates de servicios en $templateDir"
    }

    foreach ($serviceId in $ServiceIds) {
        $template = Join-Path $templateDir "$serviceId.xml"
        if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
            throw "Falta template WinSW para $serviceId"
        }

        $targetXml = Join-Path $serviceDir "$serviceId.xml"
        $targetExe = Get-ServiceWrapperPath -ServiceId $serviceId
        $existingService = Get-ServiceSafe $serviceId

        if ($existingService) {
            if ($existingService.Status -eq "Running") {
                Write-InstallLog -LogName "service-install.log" -Message "SERVICE_STOP_FOR_UPDATE $serviceId"
                Stop-Service -Name $serviceId -ErrorAction Stop
                Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Stopped" -TimeoutSeconds 90
            }

            Write-InstallLog -LogName "service-install.log" -Message "SERVICE_UNINSTALL_FOR_UPDATE $serviceId"
            if (Test-Path -LiteralPath $targetExe -PathType Leaf) {
                try {
                    Invoke-LoggedCommand `
                        -FilePath $targetExe `
                        -ArgumentList @("uninstall") `
                        -LogName "service-install.log"
                } catch {
                    if (Get-ServiceSafe $serviceId) {
                        Write-InstallLog -LogName "service-install.log" -Message ("SERVICE_UNINSTALL_FALLBACK_SC $serviceId " + $_.Exception.Message)
                        $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
                        Invoke-LoggedCommand `
                            -FilePath $scExe `
                            -ArgumentList @("delete", $serviceId) `
                            -LogName "service-install.log"
                    } else {
                        Write-InstallLog -LogName "service-install.log" -Message "SERVICE_UNINSTALL_EXIT_IGNORED $serviceId service_already_removed"
                    }
                }
            } else {
                $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
                Invoke-LoggedCommand `
                    -FilePath $scExe `
                    -ArgumentList @("delete", $serviceId) `
                    -LogName "service-install.log"
            }
            try {
                Wait-ServiceRemoved -ServiceId $serviceId -TimeoutSeconds 90
            } catch {
                if (Get-ServiceSafe $serviceId) {
                    Write-InstallLog -LogName "service-install.log" -Message ("SERVICE_REMOVE_WAIT_FALLBACK_SC $serviceId " + $_.Exception.Message)
                    $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
                    Invoke-LoggedCommand `
                        -FilePath $scExe `
                        -ArgumentList @("delete", $serviceId) `
                        -LogName "service-install.log"
                    Wait-ServiceRemoved -ServiceId $serviceId -TimeoutSeconds 90
                } else {
                    throw
                }
            }
        }

        if ($serviceId -eq "PicoDeGallo-PostgreSQL") {
            if (-not $PicoServiceAccount) {
                throw "PicoDeGallo-PostgreSQL requiere credencial de $Script:PicoServiceAccountName."
            }
            Install-WinSWServiceWithAccount `
                -Tokens $Tokens `
                -Template $template `
                -TargetXml $targetXml `
                -TargetExe $targetExe `
                -WinSWSource $winswSource `
                -PicoServiceAccount $PicoServiceAccount `
                -ServiceId $serviceId
        } else {
            Render-Template -Source $template -Destination $targetXml -Tokens $Tokens
            if ((Get-Content -LiteralPath $targetXml -Raw).Contains("{{")) {
                throw "XML WinSW renderizado contiene placeholders sin resolver: $targetXml"
            }
            Copy-Item -LiteralPath $winswSource -Destination $targetExe -Force

            Invoke-WinSWCommand -ServiceId $serviceId -Command "install"
            Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Stopped" -TimeoutSeconds 30
        }
        Assert-WinSWServiceFiles -ServiceId $serviceId
        Write-SafeHost "Servicio instalado: $serviceId"
    }

    Assert-WinSWServiceFilesForAll -ServiceIds $ServiceIds
    Write-InstallLog -LogName "service-install.log" -Message ("SERVICE_FILES_READY " + ($ServiceIds -join ","))

    foreach ($serviceId in $ServiceIds) {
        if (-not (Get-ServiceSafe $serviceId)) {
            throw "Servicio requerido no instalado: $serviceId"
        }
    }
}

function Quote-PostgresIdentifier {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ('"' + $Value.Replace('"', '""') + '"')
}

function Quote-PostgresLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ("'" + $Value.Replace("'", "''") + "'")
}

function Get-Utf8NoBomEncoding {
    return New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false)
}

function Get-BytePrefixHex {
    param(
        [byte[]]$Bytes,
        [int]$Count = 16
    )

    if (-not $Bytes -or $Bytes.Length -eq 0) {
        return ""
    }
    $take = [Math]::Min($Bytes.Length, $Count)
    $prefix = [byte[]]::new($take)
    [Array]::Copy($Bytes, 0, $prefix, 0, $take)
    return [System.BitConverter]::ToString($prefix).Replace("-", " ")
}

function Read-PostgresConfigLines {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "No existe archivo de configuracion PostgreSQL: $Path"
    }

    [byte[]]$bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_LEGACY_UTF16_LE_READ path=$Path"
        return [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::Unicode)
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_LEGACY_UTF16_BE_READ path=$Path"
        return [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::BigEndianUnicode)
    }
    if ($bytes -contains 0) {
        throw "Archivo $Path parece UTF-16 o contiene bytes NUL; no se puede leer de forma segura."
    }

    return [System.IO.File]::ReadAllLines($Path, (Get-Utf8NoBomEncoding))
}

function Test-PostgresConfigEncoding {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "No existe archivo de configuracion PostgreSQL: $Path"
    }

    [byte[]]$bytes = [System.IO.File]::ReadAllBytes($Path)
    $fileName = Split-Path -Leaf $Path
    $firstBytes = Get-BytePrefixHex -Bytes $bytes -Count 16
    Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_BYTES $fileName length=$($bytes.Length) firstBytes=$firstBytes"

    if ($bytes.Length -eq 0) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_ENCODING_ERROR $fileName empty"
        throw "Archivo $Path esta vacio."
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_ENCODING_ERROR $fileName utf16-le-bom"
        throw "Archivo $Path parece UTF-16 LE; debe ser UTF-8 sin BOM o ASCII."
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_ENCODING_ERROR $fileName utf16-be-bom"
        throw "Archivo $Path parece UTF-16 BE; debe ser UTF-8 sin BOM o ASCII."
    }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_ENCODING_ERROR $fileName utf8-bom"
        throw "Archivo $Path contiene BOM UTF-8; debe ser UTF-8 sin BOM o ASCII."
    }
    if ($bytes -contains 0) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_ENCODING_ERROR $fileName bytes NUL"
        throw "Archivo $Path parece UTF-16 o contiene bytes NUL."
    }

    $lines = [System.IO.File]::ReadAllLines($Path, (Get-Utf8NoBomEncoding))
    $preview = (($lines | Select-Object -First 8) -join "`n")
    if (-not [string]::IsNullOrWhiteSpace($preview)) {
        Write-InstallLog -LogName "postgres-config-validation.log" -Message ("POSTGRES_CONFIG_PREVIEW $fileName`n" + $preview)
    }
    Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_ENCODING_OK $fileName"
}

function Write-PostgresConfigText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [AllowEmptyString()][string]$Text
    )

    [System.IO.File]::WriteAllText($Path, $Text, (Get-Utf8NoBomEncoding))
    Test-PostgresConfigEncoding -Path $Path
}

function Write-PostgresConfigLines {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [AllowEmptyString()][AllowEmptyCollection()][string[]]$Lines = @(),
        [switch]$AllowEmpty
    )

    $lineArray = @($Lines) | ForEach-Object {
        if ($null -eq $_) {
            ""
        } else {
            [string]$_
        }
    }
    if ($lineArray.Count -eq 0 -and -not $AllowEmpty) {
        throw "No se escribio configuracion PostgreSQL vacia en $Path."
    }

    $text = ($lineArray -join "`r`n") + "`r`n"
    Write-PostgresConfigText -Path $Path -Text $text
}

function Test-PostgresDataDirectoryInitialized {
    param([Parameter(Mandatory = $true)][string]$DataDir)

    foreach ($fileName in @("PG_VERSION", "postgresql.conf", "pg_hba.conf")) {
        if (-not (Test-Path -LiteralPath (Join-Path $DataDir $fileName) -PathType Leaf)) {
            return $false
        }
    }
    return $true
}

function Assert-PostgresDataDirectoryInitialized {
    param([Parameter(Mandatory = $true)][string]$DataDir)

    $missing = @()
    foreach ($fileName in @("PG_VERSION", "postgresql.conf", "pg_hba.conf")) {
        if (-not (Test-Path -LiteralPath (Join-Path $DataDir $fileName) -PathType Leaf)) {
            $missing += $fileName
        }
    }
    if ($missing.Count -gt 0) {
        throw ("Directorio de datos PostgreSQL incompleto en {0}. Faltan: {1}. No se repara automaticamente; en VM/prueba limpia borre C:\ProgramData\PicoDeGallo antes de reinstalar." -f $DataDir, ($missing -join ", "))
    }
}

function Initialize-PostgresDataDirectory {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap,
        [Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential
    )

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $initdb = Join-Path $postgresBin "initdb.exe"

    if (-not (Test-Path -LiteralPath $initdb -PathType Leaf)) {
        throw "No existe initdb.exe en runtime PostgreSQL nativo."
    }
    if (Test-PostgresDataDirectoryInitialized -DataDir $dataDir) {
        Write-InstallLog "POSTGRES_DATA_EXISTS $dataDir PG_VERSION=present postgresql.conf=present pg_hba.conf=present"
        return
    }
    if (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION") -PathType Leaf) {
        Assert-PostgresDataDirectoryInitialized -DataDir $dataDir
    }

    $existing = Get-ChildItem -LiteralPath $dataDir -Force -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        throw "El directorio de datos PostgreSQL existe pero no esta inicializado completamente: $dataDir. No se repara automaticamente; en VM/prueba limpia borre C:\ProgramData\PicoDeGallo antes de reinstalar."
    }

    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"
    $dbPassword = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PASSWORD"
    $pwFile = Join-Path (Join-Path $Script:ProgramDataDir "postgres") ("picopos-pg-" + [Guid]::NewGuid().ToString("N") + ".pw")

    try {
        Set-Content -LiteralPath $pwFile -Value $dbPassword -Encoding ASCII
        try {
            Invoke-AsPicoServiceAccount `
                -Credential $Credential `
                -FilePath $initdb `
                -ArgumentList @("-D", $dataDir, "-E", "UTF8", "--locale=C", "--username=$dbUser", "--pwfile=$pwFile", "--auth=scram-sha-256") `
                -WorkingDirectory $postgresBin `
                -LogName "postgres-init.log"
        } catch {
            if (Test-PostgresDataDirectoryInitialized -DataDir $dataDir) {
                Write-InstallLog -LogName "postgres-init.log" -Message ("POSTGRES_INITDB_EXITCODE_WARNING_BUT_DATA_READY " + $_.Exception.Message)
                return
            }
            throw
        }
        Assert-PostgresDataDirectoryInitialized -DataDir $dataDir
        Write-InstallLog -LogName "postgres-init.log" -Message "POSTGRES_INITDB_RUN_AS $Script:PicoServiceAccountName"
        Write-InstallLog -LogName "postgres-init.log" -Message "POSTGRES_DATA_INITIALIZED $dataDir PG_VERSION=present"
    } finally {
        Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
    }
}

function Assert-PostgresRuntimeTools {
    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    foreach ($tool in @("postgres.exe", "pg_ctl.exe", "initdb.exe", "psql.exe", "pg_dump.exe", "pg_restore.exe", "createdb.exe")) {
        $path = Join-Path $postgresBin $tool
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Falta herramienta PostgreSQL requerida: $path"
        }
    }
}

function Invoke-PostgresRuntimeVersionChecks {
    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $checks = @(
        @{ Tool = "postgres.exe"; Command = "postgres.exe --version"; LogName = "postgres-version.log" },
        @{ Tool = "initdb.exe"; Command = "initdb.exe --version"; LogName = "initdb-version.log" },
        @{ Tool = "psql.exe"; Command = "psql.exe --version"; LogName = "psql-version.log" }
    )

    foreach ($check in $checks) {
        $tool = [string]$check.Tool
        $exe = Join-Path $postgresBin $tool
        Invoke-LoggedCommand `
            -FilePath $exe `
            -ArgumentList @("--version") `
            -WorkingDirectory $postgresBin `
            -LogName ([string]$check.LogName)
        Write-InstallLog -LogName "postgres-service.log" -Message ("POSTGRES_RUNTIME_VERSION_OK " + [string]$check.Command)
    }
}

function Set-PostgresConfigValue {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "No existe archivo de configuracion PostgreSQL: $ConfigPath"
    }

    $escaped = [regex]::Escape($Key)
    $line = "$Key = $Value"
    $originalLength = (Get-Item -LiteralPath $ConfigPath -ErrorAction Stop).Length
    $content = @(Read-PostgresConfigLines -Path $ConfigPath)
    if ($content.Count -eq 0 -and $originalLength -gt 0) {
        throw "No se pudo leer ninguna linea de postgresql.conf aunque el archivo no esta vacio: $ConfigPath"
    }

    $replaced = $false
    $newContent = @(foreach ($item in $content) {
        if (-not $replaced -and $item -match "^\s*#?\s*$escaped\s*=") {
            $replaced = $true
            $line
        } else {
            $item
        }
    })
    if (-not $replaced) {
        $newContent += $line
    }
    Write-PostgresConfigLines -Path $ConfigPath -Lines $newContent
    Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_SET key=$Key path=$ConfigPath replaced=$replaced"
}

function Set-PostgresHbaHostAuth {
    param([Parameter(Mandatory = $true)][string]$HbaPath)

    if (-not (Test-Path -LiteralPath $HbaPath -PathType Leaf)) {
        throw "No existe archivo pg_hba.conf: $HbaPath"
    }

    $desired = [ordered]@{
        "127.0.0.1/32" = "host all all 127.0.0.1/32 scram-sha-256"
        "::1/128" = "host all all ::1/128 scram-sha-256"
    }
    $seen = @{}
    $content = Read-PostgresConfigLines -Path $HbaPath
    $newContent = @()

    foreach ($line in $content) {
        $matched = $false
        foreach ($address in $desired.Keys) {
            $escapedAddress = [regex]::Escape([string]$address)
            if ($line -match "^\s*host\s+all\s+all\s+$escapedAddress\s+") {
                if (-not $seen.ContainsKey($address)) {
                    $newContent += [string]$desired[$address]
                    $seen[$address] = $true
                }
                $matched = $true
                break
            }
        }
        if (-not $matched) {
            $newContent += $line
        }
    }

    foreach ($address in $desired.Keys) {
        if (-not $seen.ContainsKey($address)) {
            $newContent += [string]$desired[$address]
        }
    }

    Write-PostgresConfigLines -Path $HbaPath -Lines $newContent
}

function Assert-PostgresConfiguredFiles {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$HbaPath,
        [Parameter(Mandatory = $true)][string]$DbPort
    )

    Test-PostgresConfigEncoding -Path $ConfigPath
    Test-PostgresConfigEncoding -Path $HbaPath

    $configText = [System.IO.File]::ReadAllText($ConfigPath, (Get-Utf8NoBomEncoding))
    if ([string]::IsNullOrWhiteSpace($configText)) {
        throw "postgresql.conf quedo vacio: $ConfigPath"
    }
    foreach ($required in @("listen_addresses = '127.0.0.1'", "port = $DbPort")) {
        if (-not $configText.Contains($required)) {
            throw "postgresql.conf no contiene configuracion requerida: $required"
        }
    }

    $hbaText = [System.IO.File]::ReadAllText($HbaPath, (Get-Utf8NoBomEncoding))
    foreach ($required in @(
        "host all all 127.0.0.1/32 scram-sha-256",
        "host all all ::1/128 scram-sha-256"
    )) {
        if (-not $hbaText.Contains($required)) {
            throw "pg_hba.conf no contiene configuracion requerida: $required"
        }
    }

    Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_REQUIRED_VALUES_OK postgresql.conf pg_hba.conf"
}

function Configure-PostgresDataDirectory {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $config = Join-Path $dataDir "postgresql.conf"
    $hba = Join-Path $dataDir "pg_hba.conf"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"

    Set-PostgresConfigValue -ConfigPath $config -Key "port" -Value $dbPort
    Set-PostgresConfigValue -ConfigPath $config -Key "listen_addresses" -Value "'127.0.0.1'"
    Set-PostgresConfigValue -ConfigPath $config -Key "timezone" -Value "'America/El_Salvador'"
    Set-PostgresConfigValue -ConfigPath $config -Key "logging_collector" -Value "off"
    Set-PostgresHbaHostAuth -HbaPath $hba
    Assert-PostgresConfiguredFiles -ConfigPath $config -HbaPath $hba -DbPort $dbPort
    Write-InstallLog -LogName "postgres-init.log" -Message "POSTGRES_CONFIGURED port=$dbPort listen_addresses=127.0.0.1 timezone=America/El_Salvador logging_collector=off hba=scram-loopback"
}

function Get-LogTailText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$Lines = 80
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }
    $tail = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue
    if (-not $tail) {
        return ""
    }
    return (($tail | ForEach-Object { [string]$_ }) -join "`n")
}

function Stop-PostgresForegroundTest {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$DataDir,
        [Parameter(Mandatory = $true)][string]$PostgresBin,
        [Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential
    )

    $pgCtl = Join-Path $PostgresBin "pg_ctl.exe"
    if (Test-Path -LiteralPath $pgCtl -PathType Leaf) {
        try {
            Invoke-AsPicoServiceAccount `
                -Credential $Credential `
                -FilePath $pgCtl `
                -ArgumentList @("-D", $DataDir, "-m", "fast", "-w", "stop") `
                -WorkingDirectory $PostgresBin `
                -LogName "postgres-foreground-test.stop.log"
        } catch {
            Write-InstallLog -LogName "postgres-foreground-test.stop.log" -Message ("PG_CTL_STOP_FAILED " + $_.Exception.Message)
        }
    }

    $Process.Refresh()
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $Process.Id -Timeout 20 -ErrorAction SilentlyContinue
    }
}

function Test-PostgresForegroundStartup {
    param([Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $postgres = Join-Path $postgresBin "postgres.exe"
    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $config = Join-Path $dataDir "postgresql.conf"
    $hba = Join-Path $dataDir "pg_hba.conf"
    $stdout = Get-NativeLogPath "postgres-foreground-test.out.log"
    $stderr = Get-NativeLogPath "postgres-foreground-test.err.log"
    $waitSeconds = 10

    if (-not (Test-Path -LiteralPath $postgres -PathType Leaf)) {
        throw "No existe postgres.exe en runtime PostgreSQL nativo."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION") -PathType Leaf)) {
        throw "No existe PG_VERSION en directorio de datos PostgreSQL: $dataDir"
    }
    Test-PostgresConfigEncoding -Path $config
    Test-PostgresConfigEncoding -Path $hba
    Write-InstallLog -LogName "postgres-config-validation.log" -Message "POSTGRES_CONFIG_PRE_FOREGROUND_OK postgresql.conf pg_hba.conf"

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_BEGIN seconds=$waitSeconds"
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_RUN_AS $Script:PicoServiceAccountName"
    Write-InstallLog -LogName "install-services.log" -Message "POSTGRES_FOREGROUND_TEST_BEGIN stdout=$stdout stderr=$stderr"

    $process = Invoke-AsPicoServiceAccount `
        -Credential $Credential `
        -FilePath $postgres `
        -ArgumentList @("-D", $dataDir) `
        -WorkingDirectory $postgresBin `
        -StdoutPath $stdout `
        -StderrPath $stderr `
        -LogName "postgres-service.log" `
        -NoWait

    Start-Sleep -Seconds $waitSeconds
    $process.Refresh()
    if (-not $process.HasExited) {
        Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_OK pid=$($process.Id)"
        Stop-PostgresForegroundTest -Process $process -DataDir $dataDir -PostgresBin $postgresBin -Credential $Credential
        return
    }

    $exitCode = $process.ExitCode
    $stdoutTail = Get-LogTailText -Path $stdout -Lines 80
    $stderrTail = Get-LogTailText -Path $stderr -Lines 80
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_FAILED exitCode=$exitCode"
    Write-InstallLog -LogName "service-install.log" -Message "POSTGRES_FOREGROUND_TEST_FAILED exitCode=$exitCode"
    if (-not [string]::IsNullOrWhiteSpace($stdoutTail)) {
        Write-InstallLog -LogName "service-install.log" -Message ("POSTGRES_FOREGROUND_STDOUT_TAIL`n" + $stdoutTail)
    }
    if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
        Write-InstallLog -LogName "service-install.log" -Message ("POSTGRES_FOREGROUND_STDERR_TAIL`n" + $stderrTail)
    }
    Write-SafeHost "PostgreSQL foreground test fallo con codigo $exitCode."
    if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
        Write-SafeHost $stderrTail
    }
    if ($stderrTail -match "Execution of PostgreSQL by a user with administrative permissions is not permitted") {
        throw "PostgreSQL todavia se ejecuto como usuario administrador. La prueba foreground debe correr como .\$Script:PicoServiceAccountName. Revise $stderr"
    }
    throw "PostgreSQL foreground test fallo con codigo $exitCode. Revise $stderr"
}

function Wait-PostgresReady {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $pgIsReady = Join-Path $postgresBin "pg_isready.exe"
    if (-not (Test-Path -LiteralPath $pgIsReady -PathType Leaf)) {
        throw "Falta pg_isready.exe en runtime PostgreSQL nativo."
    }

    $dbHost = Get-RequiredEnvValue -Map $EnvMap -Name "DB_HOST"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"
    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"

    for ($i = 0; $i -lt 60; $i++) {
        & $pgIsReady -h $dbHost -p $dbPort -U $dbUser | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-InstallLog "POSTGRES_READY $dbHost`:$dbPort"
            Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_READY $dbHost`:$dbPort"
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "PostgreSQL no quedo listo para configuracion inicial."
}

function Ensure-ApplicationDatabase {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $psql = Join-Path $postgresBin "psql.exe"
    $createdb = Join-Path $postgresBin "createdb.exe"
    foreach ($tool in @($psql, $createdb)) {
        if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
            throw "Falta herramienta PostgreSQL: $tool"
        }
    }

    $dbHost = Get-RequiredEnvValue -Map $EnvMap -Name "DB_HOST"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"
    $dbName = Get-RequiredEnvValue -Map $EnvMap -Name "DB_NAME"
    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"
    $dbPassword = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PASSWORD"
    $pgEnv = @{ PGPASSWORD = $dbPassword }
    $roleSql = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-role-" + [Guid]::NewGuid().ToString("N") + ".sql")
    $escapedDbUser = $dbUser.Replace("'", "''")

    $roleExists = Invoke-LoggedCommand `
        -FilePath $psql `
        -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-tAc", "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$escapedDbUser';") `
        -LogName "db-setup.log" `
        -Environment $pgEnv `
        -ReturnStdout
    if (($roleExists -join "").Trim() -eq "1") {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_ROLE_EXISTS name=$dbUser"
    } else {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_ROLE_MISSING_WILL_CREATE name=$dbUser"
    }

    try {
        $roleNameLiteral = Quote-PostgresLiteral -Value $dbUser
        $roleNameIdentifier = Quote-PostgresIdentifier -Value $dbUser
        $passwordLiteral = Quote-PostgresLiteral -Value $dbPassword
        @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = $roleNameLiteral) THEN
        CREATE ROLE $roleNameIdentifier WITH LOGIN PASSWORD $passwordLiteral;
    ELSE
        ALTER ROLE $roleNameIdentifier WITH LOGIN PASSWORD $passwordLiteral;
    END IF;
END
`$`$;
"@ | Set-Content -LiteralPath $roleSql -Encoding UTF8

        Invoke-LoggedCommand `
            -FilePath $psql `
            -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-f", $roleSql) `
            -LogName "db-setup.log" `
            -Environment $pgEnv
    } finally {
        Remove-Item -LiteralPath $roleSql -Force -ErrorAction SilentlyContinue
    }

    $escapedDbName = $dbName.Replace("'", "''")
    $exists = Invoke-LoggedCommand `
        -FilePath $psql `
        -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-tAc", "SELECT 1 FROM pg_database WHERE datname = '$escapedDbName';") `
        -LogName "db-setup.log" `
        -Environment $pgEnv `
        -ReturnStdout

    if (($exists -join "").Trim() -ne "1") {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_MISSING_WILL_CREATE name=$dbName owner=$dbUser"
        Invoke-LoggedCommand `
            -FilePath $createdb `
            -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-O", $dbUser, $dbName) `
            -LogName "db-setup.log" `
            -Environment $pgEnv
    } else {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_EXISTS name=$dbName"
    }
}

function Render-Caddyfile {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $template = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile.template"
    $caddyfile = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile"
    if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
        throw "Falta Caddyfile.template en runtime nativo."
    }

    $bind = [string]$EnvMap["APP_BIND_ADDRESS"]
    if ([string]::IsNullOrWhiteSpace($bind)) { $bind = "127.0.0.1" }
    $port = [string]$EnvMap["APP_HTTP_PORT"]
    if ([string]::IsNullOrWhiteSpace($port)) { $port = "9282" }

    (Get-Content -LiteralPath $template -Raw).
        Replace("{{APP_BIND_ADDRESS}}", $bind).
        Replace("{{APP_HTTP_PORT}}", $port).
        Replace("{{PROGRAM_FILES_DIR}}", $Script:ProgramFilesDir.Replace("\", "/")).
        Replace("{{PROGRAM_DATA_DIR}}", $Script:ProgramDataDir.Replace("\", "/")) |
        Set-Content -LiteralPath $caddyfile -Encoding UTF8

    if (-not (Test-Path -LiteralPath $caddyfile -PathType Leaf)) {
        throw "No se genero Caddyfile final: $caddyfile"
    }
    if ((Get-Content -LiteralPath $caddyfile -Raw).Contains("{{")) {
        throw "Caddyfile final contiene placeholders sin resolver: $caddyfile"
    }
    Write-InstallLog "CADDYFILE_RENDERED $caddyfile"

    $caddy = Join-Path $Script:ProgramFilesDir "caddy\caddy.exe"
    if (-not (Test-Path -LiteralPath $caddy -PathType Leaf)) {
        throw "No existe caddy.exe en runtime nativo."
    }
    Invoke-LoggedCommand `
        -FilePath $caddy `
        -ArgumentList @("validate", "--config", $caddyfile) `
        -WorkingDirectory (Join-Path $Script:ProgramFilesDir "caddy") `
        -LogName "caddy-validate.log"
    Write-InstallLog -LogName "caddy-validate.log" -Message "CADDYFILE_VALIDATE_OK $caddyfile"
}

function Validate-EmbeddedPythonImports {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("-c", "import django, waitress, psycopg2, requests; print('Python runtime OK')") `
        -LogName "python-runtime.log"
}

function Get-DjangoEnvironment {
    return @{
        DJANGO_ENV_FILE = (Get-EnvPath)
        DOTENV_OVERRIDE = "false"
        DJANGO_SETTINGS_MODULE = "config.settings"
        PYTHONUNBUFFERED = "1"
    }
}

function Invoke-DjangoManage {
    param(
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$LogName
    )

    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "No existe python.exe en runtime nativo."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $backend "manage.py") -PathType Leaf)) {
        throw "No existe backend Django en $backend"
    }

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $backend `
        -Environment (Get-DjangoEnvironment) `
        -LogName $LogName
}

function Assert-DjangoRuntimePayload {
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    $requiredPaths = @(
        "manage.py",
        "config\__init__.py",
        "config\settings.py",
        "config\wsgi.py",
        "config\asgi.py",
        "apps\core\management\commands\check_runtime_config.py",
        "apps\users\management\commands\bootstrap_initial_admin.py",
        "apps\dte\management\commands\dte_outbox_worker.py",
        "apps\dte\management\commands\dte_monitor.py"
    )

    foreach ($relative in $requiredPaths) {
        $path = Join-Path $backend $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Backend runtime incompleto: falta $path"
        }
    }
    Write-InstallLog -LogName "backend-runtime.log" -Message "DJANGO_RUNTIME_PAYLOAD_OK backend=$backend"
}

function Validate-DjangoRuntime {
    Assert-DjangoRuntimePayload
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    $script = @"
import importlib
import os

module = os.environ.get("DJANGO_SETTINGS_MODULE") or "config.settings"
print("DJANGO_SETTINGS_MODULE=" + module)
importlib.import_module(module)
importlib.import_module("config.wsgi")
print("DJANGO_SETTINGS_IMPORT_OK")
"@

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("-c", $script) `
        -WorkingDirectory $backend `
        -Environment (Get-DjangoEnvironment) `
        -LogName "backend-runtime.log"

    Invoke-DjangoManage `
        -ArgumentList @("manage.py", "help", "check_runtime_config") `
        -LogName "backend-runtime.log"

    Write-InstallLog -LogName "backend-runtime.log" -Message "DJANGO_MANAGEMENT_COMMAND_OK check_runtime_config"
}

function Run-DjangoCheckRuntime {
    Invoke-DjangoManage `
        -ArgumentList @("manage.py", "check_runtime_config", "--strict") `
        -LogName "check-runtime-config.log"
}

function Run-DjangoMigrate {
    Invoke-DjangoManage `
        -ArgumentList @("manage.py", "migrate", "--noinput") `
        -LogName "migrate.log"
}

function Run-DjangoCollectstatic {
    Invoke-DjangoManage `
        -ArgumentList @("manage.py", "collectstatic", "--noinput") `
        -LogName "collectstatic.log"
}

function Run-DjangoSetup {
    Run-DjangoCheckRuntime
    Run-DjangoMigrate
    Run-DjangoCollectstatic
}

function Run-InitialAdminBootstrap {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "bootstrap_initial_admin") `
        -WorkingDirectory $backend `
        -Environment (Get-DjangoEnvironment) `
        -LogName "bootstrap-admin.log"
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            $status = [int]$response.StatusCode
            if ($status -ge 200 -and $status -lt 300) {
                Write-InstallLog -LogName "healthcheck.log" -Message "HTTP_OK $Name $Uri status=$status"
                return
            }
            $lastError = "status=$status"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-InstallLog -LogName "healthcheck.log" -Message "HTTP_FAILED $Name $Uri $lastError"
    throw "Validacion HTTP fallo para $Name ($Uri): $lastError"
}

function Start-BackendService {
    Start-WinSWService -ServiceId "PicoDeGallo-Backend"
    Wait-HttpOk -Name "backend-ready-direct" -Uri "http://127.0.0.1:8000/api/health/ready/" -TimeoutSeconds 120
}

function Start-DteServices {
    Start-WinSWService -ServiceId "PicoDeGallo-DTE-Worker"
    Start-WinSWService -ServiceId "PicoDeGallo-DTE-Monitor"
}

function Start-CaddyService {
    Start-WinSWService -ServiceId "PicoDeGallo-Caddy"
}

function Validate-PostInstall {
    $appUrl = Get-AppUrl
    Wait-HttpOk -Name "caddy-root" -Uri $appUrl -TimeoutSeconds 120
    Wait-HttpOk -Name "health-live" -Uri "$appUrl/api/health/live/" -TimeoutSeconds 120
    Wait-HttpOk -Name "health-ready" -Uri "$appUrl/api/health/ready/" -TimeoutSeconds 120
    Assert-AllServicesRunning
}

function Invoke-InstallMain {
    $Script:NativeEnvMap = $null
    $Script:PicoServiceAccount = $null
    $Script:WinSWTokens = $null
    $Script:DatabaseHost = $null
    $Script:DatabasePort = 0

    $Script:InstallPhase = "prepare-directories"
    $Script:LastInstallStep = "prepare-directories"
    foreach ($dir in @("config", "media", "static", "dte_logs", "backups", "diagnostics", "logs", "postgres\data")) {
        New-DirectorySafe (Join-Path $Script:ProgramDataDir $dir)
    }

    $Script:InstallPhase = "archive-existing-logs"
    $Script:LastInstallStep = "archive-existing-logs"
    Stop-ExistingServicesForLogArchive
    Archive-ExistingNativeLogs
    Write-InstallLog "INSTALL_SERVICES_BEGIN Version=$(Get-InstalledVersionForInstallLog) ProgramFiles=$Script:ProgramFilesDir ProgramData=$Script:ProgramDataDir"

    Invoke-InstallStep -Name "assert-admin" -ScriptBlock {
        Assert-Admin
        if ($Script:PicoServiceAccountName -ne "PicoDeGalloSvc") {
            throw "Cuenta de servicio PostgreSQL inesperada: $Script:PicoServiceAccountName"
        }
    }

    Invoke-InstallStep -Name "start-transcript" -ScriptBlock {
        Start-InstallTranscriptSafe
    }

    Invoke-InstallStep -Name "init-env" -ScriptBlock {
        if (-not (Test-Path -LiteralPath (Get-EnvPath) -PathType Leaf)) {
            & "$PSScriptRoot\init-env.ps1"
        } else {
            Write-InstallLog "INIT_ENV_ALREADY_EXISTS target=$(Get-EnvPath)"
        }
    }

    Invoke-InstallStep -Name "read-env-and-validate-dte" -ScriptBlock {
        $Script:NativeEnvMap = Read-NativeEnv
        Test-DteEnv | Out-Null
    }

    Invoke-InstallStep -Name "ensure-service-account" -ScriptBlock {
        $Script:PicoServiceAccount = Ensure-PicoServiceAccount
    }

    Invoke-InstallStep -Name "permissions" -ScriptBlock {
        Grant-PicoServiceAccountPermissions -Account $Script:PicoServiceAccount
    }

    Invoke-InstallStep -Name "render-services-precheck" -ScriptBlock {
        Assert-ServiceTemplatesAvailable
        $Script:WinSWTokens = @{
            PROGRAM_FILES_DIR = $Script:ProgramFilesDir
            PROGRAM_DATA_DIR = $Script:ProgramDataDir
            POSTGRES_BIN_DIR = (Join-Path $Script:ProgramFilesDir "postgres\bin")
            POSTGRES_DATA_DIR = (Join-Path $Script:ProgramDataDir "postgres\data")
            PICO_SERVICE_ACCOUNT_XML = New-WinSWServiceAccountXml
            PYTHON_EXE = (Join-Path $Script:ProgramFilesDir "python\python.exe")
            BACKEND_DIR = (Join-Path $Script:ProgramFilesDir "backend")
            ENV_FILE = (Get-EnvPath)
            CADDY_EXE = (Join-Path $Script:ProgramFilesDir "caddy\caddy.exe")
            APP_HTTP_PORT = if ([string]::IsNullOrWhiteSpace([string]$Script:NativeEnvMap["APP_HTTP_PORT"])) { "9282" } else { [string]$Script:NativeEnvMap["APP_HTTP_PORT"] }
            APP_BIND_ADDRESS = if ([string]::IsNullOrWhiteSpace([string]$Script:NativeEnvMap["APP_BIND_ADDRESS"])) { "127.0.0.1" } else { [string]$Script:NativeEnvMap["APP_BIND_ADDRESS"] }
        }
    }

    Invoke-InstallStep -Name "validate-python-runtime" -ScriptBlock {
        Validate-EmbeddedPythonImports
    }

    Invoke-InstallStep -Name "validate-postgres-runtime" -ScriptBlock {
        Assert-PostgresRuntimeTools
        Invoke-PostgresRuntimeVersionChecks
    }

    Invoke-InstallStep -Name "initdb" -ScriptBlock {
        Initialize-PostgresDataDirectory -EnvMap $Script:NativeEnvMap -Credential ($Script:PicoServiceAccount.Credential)
    }

    Invoke-InstallStep -Name "configure-postgres" -ScriptBlock {
        Configure-PostgresDataDirectory -EnvMap $Script:NativeEnvMap
        Grant-PicoServiceAccountPermissions -Account $Script:PicoServiceAccount
    }

    Invoke-InstallStep -Name "postgres-foreground-test" -ScriptBlock {
        Test-PostgresForegroundStartup -Credential ($Script:PicoServiceAccount.Credential)
    }

    Invoke-InstallStep -Name "install-postgres-service" -ScriptBlock {
        Install-WinSWServices -Tokens $Script:WinSWTokens -ServiceIds @("PicoDeGallo-PostgreSQL") -PicoServiceAccount $Script:PicoServiceAccount
        Assert-WinSWServiceFilesForAll -ServiceIds @("PicoDeGallo-PostgreSQL")
    }

    Invoke-InstallStep -Name "start-postgres" -ScriptBlock {
        Start-WinSWService -ServiceId "PicoDeGallo-PostgreSQL"
        $Script:DatabaseHost = Get-RequiredEnvValue -Map $Script:NativeEnvMap -Name "DB_HOST"
        $Script:DatabasePort = [int](Get-RequiredEnvValue -Map $Script:NativeEnvMap -Name "DB_PORT")
        Wait-TcpPort -HostName $Script:DatabaseHost -Port $Script:DatabasePort -TimeoutSeconds 60 -ServiceId "PicoDeGallo-PostgreSQL"
        Wait-PostgresReady -EnvMap $Script:NativeEnvMap
    }

    Invoke-InstallStep -Name "setup-database" -ScriptBlock {
        Ensure-ApplicationDatabase -EnvMap $Script:NativeEnvMap
    }

    Invoke-InstallStep -Name "validate-backend-runtime" -ScriptBlock {
        Validate-DjangoRuntime
    }

    Invoke-InstallStep -Name "check-runtime-config" -ScriptBlock {
        Run-DjangoCheckRuntime
    }

    Invoke-InstallStep -Name "migrate" -ScriptBlock {
        Run-DjangoMigrate
    }

    Invoke-InstallStep -Name "collectstatic" -ScriptBlock {
        Run-DjangoCollectstatic
    }

    Invoke-InstallStep -Name "bootstrap-admin" -ScriptBlock {
        Run-InitialAdminBootstrap
    }

    Invoke-InstallStep -Name "install-backend" -ScriptBlock {
        Install-WinSWServices -Tokens $Script:WinSWTokens -ServiceIds @("PicoDeGallo-Backend")
        Start-BackendService
    }

    Invoke-InstallStep -Name "install-dte-services" -ScriptBlock {
        Install-WinSWServices -Tokens $Script:WinSWTokens -ServiceIds @("PicoDeGallo-DTE-Worker", "PicoDeGallo-DTE-Monitor")
        Start-DteServices
    }

    Invoke-InstallStep -Name "render-caddyfile" -ScriptBlock {
        Render-Caddyfile -EnvMap $Script:NativeEnvMap
    }

    Invoke-InstallStep -Name "install-caddy" -ScriptBlock {
        Install-WinSWServices -Tokens $Script:WinSWTokens -ServiceIds @("PicoDeGallo-Caddy")
        Start-CaddyService
    }

    Invoke-InstallStep -Name "healthcheck" -ScriptBlock {
        Assert-WinSWServiceFilesForAll
        Validate-PostInstall
    }

    foreach ($svc in $Script:Services) {
        Write-SafeHost "Servicio listo: $svc"
    }

    Write-InstallLog "INSTALL_SERVICES_SUCCESS"
}

try {
    Invoke-InstallMain
} catch {
    Write-InstallException -ErrorRecord $_
    Write-SafeHost ("Instalacion de servicios fallo en paso {0}: {1}" -f $Script:LastInstallStep, $_.Exception.Message)
    exit 1
} finally {
    Stop-InstallTranscriptSafe
}
