; Inno Setup script for AI-ditor Plus (Windows)
; Build with: iscc aiditor_plus_setup.iss

#define MyAppName "AI-ditor Plus"
#define MyAppVersion "1.0"
#define MyAppPublisher "Alparslan Guvenc"
#define MyAppExeName "AIditorPlus.exe"

[Setup]
AppId={{B3E1A4F2-9C7D-4E8B-AF2E-12345678ABCD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=AIditorPlus_Setup
SetupIconFile=icon_plus.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
LicenseFile=LICENSE

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
