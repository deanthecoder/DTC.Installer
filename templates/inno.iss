; Generated via Installer/pack.py token replacement

#define MyAppName "{{ProductName}}"
#define MyAppVersion "{{Version}}"
#define MyAppPublisher "{{CompanyName}}"
#define MyAppURL "{{PublisherUrl}}"
#define MyAppExeName "{{Executable}}"
#define MyAppAppId "{{AppId}}"
#define MyAppSourceDir "{{SourceDir}}"
#define MyAppOutputDir "{{OutputDir}}"
#define MyAppOutputBase "{{OutputBase}}"
#define MyAppIcon "{{SetupIconFile}}"

[Setup]
AppId={#MyAppAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir={#MyAppOutputDir}
OutputBaseFilename={#MyAppOutputBase}
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
#if MyAppIcon != ""
SetupIconFile={#MyAppIcon}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\3rdParty\oalinst.exe"; Description: "Installing OpenAL"; Parameters:"/s"; Flags: skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
