[Setup]
AppName=FortiGate Backup Manager
AppVersion=1.0.0
DefaultDirName={pf}\FortiGate Backup Manager
DefaultGroupName=FortiGate Backup Manager
OutputDir=.
OutputBaseFilename=FGBM-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "..\dist\fgbm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FortiGate Backup Manager"; Filename: "{app}\fgbm.exe"
Name: "{commondesktop}\FortiGate Backup Manager"; Filename: "{app}\fgbm.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked
