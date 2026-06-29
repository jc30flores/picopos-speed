#define MyAppName "Pico de Gallo"
#ifndef MyAppVersion
#define MyAppVersion "0.0.0-dev"
#endif
#ifndef SourceRoot
#define SourceRoot "..\..\..\release\windows-native"
#endif
#define ProgramFilesPayload SourceRoot + "\ProgramFiles\PicoDeGallo"
#define ProgramDataPayload SourceRoot + "\ProgramData\PicoDeGallo"

[Setup]
AppId={{A8B7AF46-36A8-4D4D-B94E-1C0DE0000001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Meka Technologies
DefaultDirName={autopf}\PicoDeGallo
DefaultGroupName=Pico de Gallo
PrivilegesRequired=admin
OutputBaseFilename=PicoDeGallo-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableDirPage=no
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName={#MyAppName}

[Dirs]
Name: "{commonappdata}\PicoDeGallo"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\config"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\postgres\data"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\media"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\static"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\dte_logs"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\logs"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\backups"; Permissions: users-modify
Name: "{commonappdata}\PicoDeGallo\diagnostics"; Permissions: users-modify

[Files]
Source: "{#ProgramFilesPayload}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "{#ProgramDataPayload}\config\.env.example"; DestDir: "{commonappdata}\PicoDeGallo\config"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#ProgramFilesPayload}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\Pico de Gallo\Abrir Pico de Gallo"; Filename: "http://127.0.0.1:9282"
Name: "{autoprograms}\Pico de Gallo\Iniciar Pico de Gallo"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\start.ps1"""
Name: "{autoprograms}\Pico de Gallo\Detener Pico de Gallo"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\stop.ps1"""
Name: "{autoprograms}\Pico de Gallo\Estado Pico de Gallo"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\status.ps1"""
Name: "{autoprograms}\Pico de Gallo\Diagnóstico Pico de Gallo"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\diagnostics.ps1"""
Name: "{autoprograms}\Pico de Gallo\Backup Pico de Gallo"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\backup.ps1"""
Name: "{autoprograms}\Pico de Gallo\Restaurar Backup Pico de Gallo"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\restore.ps1"""

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\init-env.ps1"""; StatusMsg: "Creando configuración local..."; Flags: runhidden; Check: EnvMissing
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\install-services.ps1"""; StatusMsg: "Instalando servicios de Pico de Gallo..."; Flags: runhidden
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\start.ps1"""; StatusMsg: "Iniciando servicios..."; Flags: runhidden

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\uninstall-services.ps1"""; Flags: runhidden; RunOnceId: "StopPicoDeGalloServices"

[Code]
function EnvMissing: Boolean;
begin
  Result := not FileExists(ExpandConstant('{commonappdata}\PicoDeGallo\config\.env'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then begin
    if DirExists(ExpandConstant('{app}')) then begin
      Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\scripts\stop.ps1') + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\scripts\backup.ps1') + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    MsgBox('Los datos de Pico de Gallo se conservaron en C:\ProgramData\PicoDeGallo', mbInformation, MB_OK);
  end;
end;
