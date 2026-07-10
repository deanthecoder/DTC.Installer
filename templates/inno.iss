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
#define MyAppShowRunOnStartupTask {{ShowRunOnStartupTask}}
#define MyAppCommandLine {{CommandLine}}

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
#if MyAppCommandLine
ChangesEnvironment=yes
#endif
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
#if !MyAppCommandLine
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
#endif
#if MyAppShowRunOnStartupTask
Name: "startup"; Description: "Run {#MyAppName} when Windows starts"; GroupDescription: "Startup options:"; Flags: unchecked
#endif

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
#if !MyAppCommandLine
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
#endif

#if MyAppShowRunOnStartupTask
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

#endif

[Run]
Filename: "{app}\3rdParty\oalinst.exe"; Description: "Installing OpenAL"; Parameters:"/s"; Flags: skipifdoesntexist
#if !MyAppCommandLine
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
#endif

#if MyAppCommandLine
[Code]
function NormalisePathEntry(Value: string): string;
begin
  Result := Trim(Value);
  while (Length(Result) > 3) and (Result[Length(Result)] = '\') do
    Delete(Result, Length(Result), 1);
end;

function PathContains(Paths: string; Entry: string): Boolean;
var
  Remaining: string;
  Current: string;
  Separator: Integer;
begin
  Result := False;
  Remaining := Paths;
  repeat
    Separator := Pos(';', Remaining);
    if Separator = 0 then
    begin
      Current := Remaining;
      Remaining := '';
    end
    else
    begin
      Current := Copy(Remaining, 1, Separator - 1);
      Delete(Remaining, 1, Separator);
    end;
    if CompareText(NormalisePathEntry(Current), NormalisePathEntry(Entry)) = 0 then
    begin
      Result := True;
      Exit;
    end;
  until Remaining = '';
end;

procedure AddToUserPath(Entry: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then
    Paths := '';
  if PathContains(Paths, Entry) then
    Exit;
  if (Paths <> '') and (Paths[Length(Paths)] <> ';') then
    Paths := Paths + ';';
  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Paths + Entry);
end;

procedure RemoveFromUserPath(Entry: string);
var
  Paths: string;
  Remaining: string;
  Current: string;
  Updated: string;
  Separator: Integer;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then
    Exit;
  Remaining := Paths;
  Updated := '';
  repeat
    Separator := Pos(';', Remaining);
    if Separator = 0 then
    begin
      Current := Remaining;
      Remaining := '';
    end
    else
    begin
      Current := Copy(Remaining, 1, Separator - 1);
      Delete(Remaining, 1, Separator);
    end;
    if (Trim(Current) <> '') and
       (CompareText(NormalisePathEntry(Current), NormalisePathEntry(Entry)) <> 0) then
    begin
      if Updated <> '' then
        Updated := Updated + ';';
      Updated := Updated + Current;
    end;
  until Remaining = '';
  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Updated);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AddToUserPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveFromUserPath(ExpandConstant('{app}'));
end;
#endif
