#ifndef AppVersion
  #error AppVersion must be supplied with /DAppVersion=x.y.z
#endif
#ifndef SourceDir
  #error SourceDir must be supplied with /DSourceDir=path
#endif
#ifndef OutputDir
  #error OutputDir must be supplied with /DOutputDir=path
#endif

#define WebView2ClientGuid "{F1E7E5C7-00A0-4D7C-8F7D-7A7B7586A3D4}"

[Setup]
AppId={{61D4D665-79A6-4C85-A5D0-FE262538F79C}
AppName=InfiniteCanvas Desktop
AppVersion={#AppVersion}
AppVerName=InfiniteCanvas Desktop {#AppVersion}
AppPublisher=wwfoliage
AppPublisherURL=https://github.com/wwfoliage/InfiniteCanvas-Desktop
AppSupportURL=https://github.com/wwfoliage/InfiniteCanvas-Desktop/issues
AppUpdatesURL=https://github.com/wwfoliage/InfiniteCanvas-Desktop/releases
#ifdef SmokeTestRoot
DefaultDirName={#SmokeTestRoot}
UsePreviousAppDir=no
#else
DefaultDirName={localappdata}\Programs\InfiniteCanvas
#endif
DefaultGroupName=InfiniteCanvas
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir={#OutputDir}
OutputBaseFilename=InfiniteCanvas-Setup-{#AppVersion}
SetupIconFile=InfiniteCanvas.ico
UninstallDisplayIcon={app}\InfiniteCanvas.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName=InfiniteCanvas Desktop
VersionInfoDescription=InfiniteCanvas Desktop Installer
#ifdef SmokeTestRoot
Uninstallable=no
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
#ifndef SmokeTestRoot
Name: "{group}\InfiniteCanvas"; Filename: "{app}\InfiniteCanvas.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\InfiniteCanvas"; Filename: "{app}\InfiniteCanvas.exe"; WorkingDir: "{app}"; Tasks: desktopicon
#endif

[Run]
#ifndef SmokeTestRoot
Filename: "{app}\InfiniteCanvas.exe"; Description: "{cm:LaunchProgram,InfiniteCanvas}"; Flags: nowait postinstall skipifsilent
#endif

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RuntimeDir: String;
  ExecutablePath: String;
begin
  Result := '';
  RuntimeDir := ExpandConstant('{app}\_internal');
  ExecutablePath := ExpandConstant('{app}\InfiniteCanvas.exe');

  if DirExists(RuntimeDir) and
     (not DelTree(RuntimeDir, True, True, True)) then
  begin
    Result := 'The previous InfiniteCanvas runtime could not be removed.';
    Exit;
  end;

  if FileExists(ExecutablePath) and
     (not DeleteFile(ExecutablePath)) then
  begin
    Result := 'The previous InfiniteCanvas executable could not be removed.';
    Exit;
  end;
end;

function HasWebView2Runtime: Boolean;
var
  Version: String;
  ClientKey: String;
begin
  ClientKey := 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + '{F1E7E5C7-00A0-4D7C-8F7D-7A7B7586A3D4}';
  Result :=
    (RegQueryStringValue(HKCU, ClientKey, 'pv', Version) and (Version <> '')) or
    (RegQueryStringValue(HKLM32, ClientKey, 'pv', Version) and (Version <> '')) or
    (RegQueryStringValue(HKLM64, ClientKey, 'pv', Version) and (Version <> ''));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
#ifndef SmokeTestRoot
  if (CurStep = ssPostInstall) and (not HasWebView2Runtime) then
  begin
    MsgBox(
      'Microsoft Edge WebView2 Runtime was not detected.' + #13#10 + #13#10 +
      'Install it before starting InfiniteCanvas:' + #13#10 +
      'https://developer.microsoft.com/microsoft-edge/webview2/',
      mbInformation,
      MB_OK
    );
  end;
#endif
end;
