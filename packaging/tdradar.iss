#define MyAppName "TD Radar"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "TD Radar contributors"
#define MyAppURL "https://github.com/PlasmaPerfuma/speit-td-radar"

[Setup]
AppId={{7C0F3D1E-2A9B-4B7A-9E2D-3E6B5C8F1A42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\TD Radar
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=TD-Radar-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\tdradar.exe
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\tdradar\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\data\llm_config.example.json"; DestDir: "{userappdata}\TD Radar"; DestName: "llm_config.json"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\data\canvas_token.example.txt"; DestDir: "{userappdata}\TD Radar"; DestName: "canvas_token.txt"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\TD Radar"; Filename: "{app}\tdradar.exe"; Parameters: "doctor"; WorkingDir: "{app}"
Name: "{userdesktop}\TD Radar"; Filename: "{app}\tdradar.exe"; Parameters: "doctor"; WorkingDir: "{app}"

[Run]
Filename: "{app}\tdradar.exe"; Parameters: "doctor"; Description: "Run TD Radar doctor"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
