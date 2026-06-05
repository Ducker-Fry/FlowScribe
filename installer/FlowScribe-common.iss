#define MyAppName "FlowScribe"
#define MyAppVersion "0.3.3"
#define MyAppPublisher "FlowScribe contributors"
#define MyAppURL "https://github.com/Ducker-Fry/FlowScribe"
#ifndef BuildFlavor
#define BuildFlavor "offline"
#endif
#ifndef OnlineVersion
#define OnlineVersion ""
#endif
#ifndef OnlineCliZipName
#define OnlineCliZipName ""
#endif
#ifndef OnlineGuiZipName
#define OnlineGuiZipName ""
#endif
#ifndef OnlineCliUrl
#define OnlineCliUrl ""
#endif
#ifndef OnlineGuiUrl
#define OnlineGuiUrl ""
#endif
#ifndef OnlineCliSha256
#define OnlineCliSha256 ""
#endif
#ifndef OnlineGuiSha256
#define OnlineGuiSha256 ""
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousPrivileges=no
OutputDir=build\installer
ChangesEnvironment=no
UninstallDisplayIcon={app}\GUI\FlowScribeGUI.exe
SetupLogging=yes

[Types]
Name: "full"; Description: "GUI + CLI + docs"
Name: "compact"; Description: "GUI + docs"
Name: "cli"; Description: "CLI only"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "gui"; Description: "Desktop GUI"; Types: full compact custom
Name: "cli"; Description: "Command-line tools"; Types: full cli custom
Name: "docs"; Description: "Local help docs"; Types: full compact cli custom
Name: "helper"; Description: "Installer helper runtime"; Flags: fixed

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Components: gui; Flags: checkedonce
Name: "autostart"; Description: "Start FlowScribe GUI when I sign in (writes to Startup folder)"; GroupDescription: "Startup:"; Components: gui
Name: "addtopath"; Description: "Add FlowScribe CLI to PATH"; GroupDescription: "Command line:"; Components: cli

[Icons]
Name: "{group}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui
Name: "{group}\FlowScribe CLI"; Filename: "{app}\CLI\FlowScribe.exe"; Components: cli
Name: "{group}\FlowScribe Help"; Filename: "{code:GetDocsIndexPath}"; Components: docs; Check: HasDocsIndex
Name: "{group}\Uninstall FlowScribe"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui; Check: ShouldCreateDesktopShortcut
Name: "{userstartup}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui; Check: ShouldEnableAutoStartCurrentUser
Name: "{commonstartup}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui; Check: ShouldEnableAutoStartAllUsers

[Registry]
Root: HKCU; Subkey: "Software\FlowScribe\InstallBackup"; ValueType: expandsz; ValueName: "UserPathBeforeAdd"; ValueData: "{code:GetCurrentUserPathBackup}"; Components: cli; Check: ShouldAddToPathCurrentUser; Flags: preservestringtype
Root: HKLM; Subkey: "Software\FlowScribe\InstallBackup"; ValueType: expandsz; ValueName: "SystemPathBeforeAdd"; ValueData: "{code:GetCurrentSystemPathBackup}"; Components: cli; Check: ShouldAddToPathAllUsers; Flags: preservestringtype
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{code:GetUpdatedUserPath}"; Components: cli; Check: ShouldAddToPathCurrentUser; Flags: preservestringtype
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{code:GetUpdatedSystemPath}"; Components: cli; Check: ShouldAddToPathAllUsers; Flags: preservestringtype
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open"; ValueType: string; ValueName: ""; ValueData: "Use FlowScribe to open transcript"; Components: gui; Check: ShouldRegisterJsonContextCurrentUser; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\GUI\FlowScribeGUI.exe"" ""%1"""; Components: gui; Check: ShouldRegisterJsonContextCurrentUser; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open"; ValueType: string; ValueName: ""; ValueData: "Use FlowScribe to open transcript"; Components: gui; Check: ShouldRegisterJsonContextAllUsers; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\GUI\FlowScribeGUI.exe"" ""%1"""; Components: gui; Check: ShouldRegisterJsonContextAllUsers; Flags: uninsdeletekey

[Run]
Filename: "{app}\GUI\FlowScribeGUI.exe"; Description: "Launch FlowScribe"; Flags: postinstall nowait skipifsilent unchecked; Components: gui

[Code]
const
  InstallRootMarkerName = '.flowscribe-install-root';
  ManagedDirMarkerName = '.flowscribe-managed';
  InstallerStateDirName = 'installer-state';
  UserPathBackupFileName = 'user-path-before-add.txt';
  SystemPathBackupFileName = 'system-path-before-add.txt';
  ModelsDirStateFileName = 'models-dir.txt';
  DocsDirStateFileName = 'docs-dir.txt';

var
  ShortcutsPage: TInputOptionWizardPage;
  FileAssocPage: TInputOptionWizardPage;
  ModelsPage: TInputOptionWizardPage;
  ResourcesPage: TInputDirWizardPage;
  PayloadDownloadPage: TDownloadWizardPage;
  PayloadExtractPage: TOutputMarqueeProgressWizardPage;
  DownloadPage: TOutputMsgWizardPage;
  UninstallOptionsPage: TInputOptionWizardPage;
  SelectedInstallScope: String;
  SelectedModelsDir: String;
  SelectedDocsDir: String;
  LastAutoInstallDir: String;
  OnlinePayloadsDownloaded: Boolean;
  OnlinePayloadsPrepared: Boolean;
  RemoveProgramFiles: Boolean;
  RemoveSharedResources: Boolean;
  RemoveUserData: Boolean;

function IsOfflineBuild: Boolean;
begin
  Result := '{#BuildFlavor}' = 'offline';
end;

function IsOnlineBuild: Boolean;
begin
  Result := '{#BuildFlavor}' = 'online';
end;

function GetOnlinePayloadStageRoot: String;
begin
  Result := ExpandConstant('{tmp}\flowscribe-online-staging');
end;

function GetOnlineCliArchivePath: String;
begin
  Result := ExpandConstant('{tmp}\{#OnlineCliZipName}');
end;

function GetOnlineGuiArchivePath: String;
begin
  Result := ExpandConstant('{tmp}\{#OnlineGuiZipName}');
end;

procedure DeleteDirIfPresent(DirPath: String);
begin
  if DirExists(DirPath) then
    DelTree(DirPath, True, True, True);
end;

function FormatOnlineDownloadError(FileName, Url, Details: String): String;
begin
  Result :=
    'FlowScribe could not download the required online component:' + #13#10 + #13#10 +
    'File: ' + FileName + #13#10 +
    'URL: ' + Url + #13#10 + #13#10 +
    'Reason: ' + Details + #13#10 + #13#10 +
    'Check your network connection, proxy settings, or whether the download source is reachable. Setup will now exit.';
end;

function FormatOnlineExtractError(FileName, Details: String): String;
begin
  Result :=
    'FlowScribe downloaded the online component but could not extract it:' + #13#10 + #13#10 +
    'File: ' + FileName + #13#10 +
    'Reason: ' + Details + #13#10 + #13#10 +
    'Setup will now exit.';
end;

procedure EnsureDirectoryExists(Value: String);
begin
  if (Value <> '') and (not DirExists(Value)) then
    ForceDirectories(Value);
end;

function PrepareOnlinePayloads(var ErrorMessage: String): Boolean;
var
  StageRoot: String;
begin
  Result := True;
  if (not IsOnlineBuild) or OnlinePayloadsPrepared then
    exit;

  StageRoot := GetOnlinePayloadStageRoot;
  DeleteDirIfPresent(StageRoot);
  EnsureDirectoryExists(StageRoot);

  PayloadExtractPage.Show;
  try
    PayloadExtractPage.SetText(
      'Preparing downloaded FlowScribe components',
      'Expanding verified CLI and GUI archives into a temporary staging area.'
    );
    PayloadExtractPage.Animate;

    try
      ExtractArchive(GetOnlineCliArchivePath, StageRoot, '', True, nil);
    except
      ErrorMessage := FormatOnlineExtractError('{#OnlineCliZipName}', GetExceptionMessage);
      Result := False;
      exit;
    end;

    PayloadExtractPage.Animate;

    try
      ExtractArchive(GetOnlineGuiArchivePath, StageRoot, '', True, nil);
    except
      ErrorMessage := FormatOnlineExtractError('{#OnlineGuiZipName}', GetExceptionMessage);
      Result := False;
      exit;
    end;
  finally
    PayloadExtractPage.Hide;
  end;

  if not DirExists(AddBackslash(StageRoot) + 'FlowScribe') then begin
    ErrorMessage :=
      'FlowScribe downloaded the CLI archive, but the extracted folder `FlowScribe` was not found in the staging area.' + #13#10 +
      'Setup will now exit.';
    Result := False;
    exit;
  end;

  if not DirExists(AddBackslash(StageRoot) + 'FlowScribeGUI') then begin
    ErrorMessage :=
      'FlowScribe downloaded the GUI archive, but the extracted folder `FlowScribeGUI` was not found in the staging area.' + #13#10 +
      'Setup will now exit.';
    Result := False;
    exit;
  end;

  OnlinePayloadsPrepared := True;
end;

function DownloadOnlinePayloads(var ErrorMessage: String): Boolean;
var
  DownloadCount: Integer;
begin
  Result := True;
  Log('DownloadOnlinePayloads invoked. IsOnlineBuild=' + IntToStr(Integer(IsOnlineBuild)) + ' Downloaded=' + IntToStr(Integer(OnlinePayloadsDownloaded)));
  if (not IsOnlineBuild) or OnlinePayloadsDownloaded then
    exit;

  PayloadDownloadPage.Clear;
  DownloadCount := 0;
  if WizardIsComponentSelected('cli') then begin
    PayloadDownloadPage.Add('{#OnlineCliUrl}', '{#OnlineCliZipName}', '{#OnlineCliSha256}');
    DownloadCount := DownloadCount + 1;
  end;
  if WizardIsComponentSelected('gui') then begin
    PayloadDownloadPage.Add('{#OnlineGuiUrl}', '{#OnlineGuiZipName}', '{#OnlineGuiSha256}');
    DownloadCount := DownloadCount + 1;
  end;

  if DownloadCount = 0 then
    exit;

  Log('Downloading online payload count=' + IntToStr(DownloadCount));
  PayloadDownloadPage.Show;
  try
    try
      PayloadDownloadPage.Download;
    except
      if PayloadDownloadPage.AbortedByUser then
        ErrorMessage := 'The download was canceled before FlowScribe could install all required components.'
      else if PayloadDownloadPage.LastBaseNameOrUrl = '{#OnlineCliZipName}' then
        ErrorMessage := FormatOnlineDownloadError(
          '{#OnlineCliZipName}',
          '{#OnlineCliUrl}',
          GetExceptionMessage
        )
      else if PayloadDownloadPage.LastBaseNameOrUrl = '{#OnlineGuiZipName}' then
        ErrorMessage := FormatOnlineDownloadError(
          '{#OnlineGuiZipName}',
          '{#OnlineGuiUrl}',
          GetExceptionMessage
        )
      else
        ErrorMessage := 'FlowScribe could not download one of the required online components: ' + GetExceptionMessage;
      Result := False;
      exit;
    end;
  finally
    PayloadDownloadPage.Hide;
  end;

  OnlinePayloadsDownloaded := True;
end;

procedure RefreshSelectedInstallScope;
begin
  if IsAdminInstallMode then
    SelectedInstallScope := 'machine'
  else
    SelectedInstallScope := 'user';
end;

function IsCurrentUserInstall: Boolean;
begin
  Result := SelectedInstallScope = 'user';
end;

function IsAllUsersInstall: Boolean;
begin
  Result := SelectedInstallScope = 'machine';
end;

function ShouldCreateDesktopShortcut: Boolean;
begin
  Result := WizardIsComponentSelected('gui') and ShortcutsPage.Values[0];
end;

function ShouldEnableAutoStartCurrentUser: Boolean;
begin
  Result := WizardIsComponentSelected('gui') and ShortcutsPage.Values[1] and IsCurrentUserInstall;
end;

function ShouldEnableAutoStartAllUsers: Boolean;
begin
  Result := WizardIsComponentSelected('gui') and ShortcutsPage.Values[1] and IsAllUsersInstall;
end;

function ShouldAddToPathCurrentUser: Boolean;
begin
  Result := WizardIsComponentSelected('cli') and IsCurrentUserInstall and WizardIsTaskSelected('addtopath');
end;

function ShouldAddToPathAllUsers: Boolean;
begin
  Result := WizardIsComponentSelected('cli') and IsAllUsersInstall and WizardIsTaskSelected('addtopath');
end;

function ShouldRegisterJsonContextCurrentUser: Boolean;
begin
  Result := WizardIsComponentSelected('gui') and FileAssocPage.Values[0] and IsCurrentUserInstall;
end;

function ShouldRegisterJsonContextAllUsers: Boolean;
begin
  Result := False;
end;

function GetDefaultModelsDir(ScopeValue: String): String;
begin
  if ScopeValue = 'machine' then
    Result := ExpandConstant('{commonappdata}\FlowScribe\models')
  else
    Result := ExpandConstant('{localappdata}\FlowScribe\models');
end;

function GetDefaultDocsDir(ScopeValue: String): String;
begin
  if ScopeValue = 'machine' then
    Result := ExpandConstant('{commonappdata}\FlowScribe\docs')
  else
    Result := ExpandConstant('{localappdata}\FlowScribe\docs');
end;

procedure UpdateResourceDefaults;
begin
  if SelectedInstallScope = '' then
    RefreshSelectedInstallScope;
  SelectedModelsDir := GetDefaultModelsDir(SelectedInstallScope);
  SelectedDocsDir := GetDefaultDocsDir(SelectedInstallScope);
  if Assigned(ResourcesPage) then begin
    ResourcesPage.Values[0] := SelectedModelsDir;
    ResourcesPage.Values[1] := SelectedDocsDir;
  end;
end;

function HasCommandLineDirOverride: Boolean;
begin
  Result := ExpandConstant('{param:dir|}') <> '';
end;

function BuildDefaultInstallDir(ScopeValue: String): String;
begin
  if ScopeValue = 'machine' then
    Result := ExpandConstant('{autopf}\FlowScribe')
  else
    Result := ExpandConstant('{localappdata}\Programs\FlowScribe');
end;

function GetSetupDefaultDir(Param: String): String;
begin
  RefreshSelectedInstallScope;
  Result := BuildDefaultInstallDir(SelectedInstallScope);
end;

procedure ApplyDefaultInstallDir;
var
  DefaultDir: String;
begin
  RefreshSelectedInstallScope;
  if HasCommandLineDirOverride then
    exit;

  DefaultDir := BuildDefaultInstallDir(SelectedInstallScope);
  if (Trim(WizardForm.DirEdit.Text) = '') or (WizardForm.DirEdit.Text = LastAutoInstallDir) then
    WizardForm.DirEdit.Text := DefaultDir;
  LastAutoInstallDir := DefaultDir;
end;

function NormalizePath(Value: String): String;
begin
  Result := Lowercase(RemoveBackslashUnlessRoot(Trim(Value)));
end;

function IsDriveRootPath(Value: String): Boolean;
begin
  Result := (Length(Value) = 3) and (Value[2] = ':') and (Value[3] = '\');
end;

function IsUnsafeDirectoryTarget(Value: String): Boolean;
var
  Candidate: String;
begin
  Candidate := NormalizePath(Value);
  Result := (Candidate = '') or IsDriveRootPath(Candidate);
  if Result then
    exit;

  Result :=
    (Candidate = NormalizePath(ExpandConstant('{win}'))) or
    (Candidate = NormalizePath(ExpandConstant('{sys}'))) or
    (Candidate = NormalizePath(ExpandConstant('{syswow64}'))) or
    (Candidate = NormalizePath(ExpandConstant('{autopf}'))) or
    (Candidate = NormalizePath(ExpandConstant('{commonpf}'))) or
    (Candidate = NormalizePath(ExpandConstant('{commoncf}'))) or
    (Candidate = NormalizePath(ExpandConstant('{commonappdata}'))) or
    (Candidate = NormalizePath(ExpandConstant('{localappdata}'))) or
    (Candidate = NormalizePath(ExpandConstant('{userappdata}')));
end;

function ValidateManagedDirectory(Value, Purpose: String): Boolean;
begin
  Result := not IsUnsafeDirectoryTarget(Value);
  if not Result then
    MsgBox(
      'The selected ' + Purpose + ' is too broad or points to a protected Windows location:' + #13#10 + Value + #13#10 + #13#10 +
      'Choose a dedicated FlowScribe subfolder instead.',
      mbError,
      MB_OK
    );
end;

function GetInstallerStateDir: String;
begin
  Result := AddBackslash(ExpandConstant('{app}')) + InstallerStateDirName;
end;

procedure SaveInstallerStateValue(FileName, Value: String);
begin
  EnsureDirectoryExists(GetInstallerStateDir);
  SaveStringToFile(AddBackslash(GetInstallerStateDir) + FileName, Value, False);
end;

function LoadInstallerStateValue(FileName: String): String;
var
  LoadedValue: AnsiString;
begin
  Result := '';
  if FileExists(AddBackslash(GetInstallerStateDir) + FileName) then begin
    LoadedValue := '';
    if LoadStringFromFile(AddBackslash(GetInstallerStateDir) + FileName, LoadedValue) then
      Result := LoadedValue;
  end;
end;

procedure EnsureDirectoryMarker(DirPath, MarkerName: String);
begin
  EnsureDirectoryExists(DirPath);
  SaveStringToFile(AddBackslash(DirPath) + MarkerName, ExpandConstant('{#MyAppName}'), False);
end;

function HasDirectoryMarker(DirPath, MarkerName: String): Boolean;
begin
  Result := FileExists(AddBackslash(DirPath) + MarkerName);
end;

function BuildModelList: String;
begin
  if ModelsPage.Values[2] then begin
    Result := '';
    exit;
  end;

  Result := '';
  if ModelsPage.Values[0] then
    Result := 'small';
  if ModelsPage.Values[1] then begin
    if Result <> '' then
      Result := Result + ',';
    Result := Result + 'tiny';
  end;
end;

function BuildInstallSummary: String;
var
  ModelsSummary: String;
begin
  Result :=
    'Program directory: ' + WizardForm.DirEdit.Text + #13#10 +
    'Install scope: ' + SelectedInstallScope + #13#10;

  if WizardIsComponentSelected('cli') and WizardIsTaskSelected('addtopath') then begin
    if IsAllUsersInstall then
      Result := Result + 'PATH change: machine-level PATH will append ' + AddBackslash(WizardForm.DirEdit.Text) + 'CLI and store a backup under Software\FlowScribe\InstallBackup.' + #13#10
    else
      Result := Result + 'PATH change: current-user PATH will append ' + AddBackslash(WizardForm.DirEdit.Text) + 'CLI and store a backup under Software\FlowScribe\InstallBackup.' + #13#10;
    Result := Result + 'Environment refresh: disabled in setup; new shells may need sign-out or Explorer restart to observe PATH changes.' + #13#10;
  end else begin
    Result := Result + 'PATH change: none.' + #13#10;
  end;

  if WizardIsComponentSelected('gui') and ShortcutsPage.Values[1] then
    Result := Result + 'Startup entry: Startup folder shortcut will be created.' + #13#10
  else
    Result := Result + 'Startup entry: none.' + #13#10;

  if ShouldRegisterJsonContextCurrentUser then
    Result := Result + 'JSON context menu: current-user right-click menu entry only.' + #13#10
  else
    Result := Result + 'JSON context menu: none.' + #13#10;

  Result := Result +
    'CLI helper action: installer will run FlowScribe CLI to write install-config.json.' + #13#10 +
    'Models directory: ' + ResourcesPage.Values[0] + #13#10;

  if WizardIsComponentSelected('docs') then
    Result := Result + 'Docs directory: ' + ResourcesPage.Values[1] + #13#10
  else
    Result := Result + 'Docs directory: not selected.' + #13#10;

  ModelsSummary := BuildModelList;
  if ModelsSummary = '' then
    Result := Result + 'Model download: skipped.'
  else
    Result := Result + 'Model download: ' + ModelsSummary + '.';
end;

procedure UpdateInstallSummary;
begin
  { TOutputMsgWizardPage exposes only the initial message text in Inno Setup 6.7.3. }
end;

procedure InitializeWizard;
begin
  RefreshSelectedInstallScope;
  ApplyDefaultInstallDir;
  OnlinePayloadsDownloaded := False;
  OnlinePayloadsPrepared := False;

  if IsOnlineBuild then begin
    PayloadDownloadPage := CreateDownloadPage(
      SetupMessage(msgWizardPreparing),
      SetupMessage(msgPreparingDesc),
      nil
    );
    PayloadDownloadPage.ShowBaseNameInsteadOfUrl := True;
    PayloadExtractPage := CreateOutputMarqueeProgressPage(
      'Preparing FlowScribe Components',
      'Extracting verified online payloads into a temporary staging area.'
    );
  end;

  ShortcutsPage := CreateInputOptionPage(
    wpSelectTasks,
    'Shortcuts And Startup',
    'Choose desktop and startup behavior',
    'Start menu entries are always created for installed components.',
    False,
    False
  );
  ShortcutsPage.Add('Create a desktop shortcut for the GUI');
  ShortcutsPage.Add('Start the GUI automatically when I sign in');
  ShortcutsPage.Values[0] := True;

  FileAssocPage := CreateInputOptionPage(
    ShortcutsPage.ID,
    'File Integration',
    'Choose safe file integration',
    'FlowScribe will add only a current-user right-click action for transcript JSON files. It will not replace the default JSON app.',
    False,
    False
  );
  FileAssocPage.Add('Add "Use FlowScribe to open transcript" to .json right-click menu');
  FileAssocPage.Values[0] := False;

  ModelsPage := CreateInputOptionPage(
    FileAssocPage.ID,
    'Model Selection',
    'Choose models to download during installation',
    'Downloads happen during setup and consume network and disk space. Skip by default and install later from Model Center if you prefer.',
    False,
    False
  );
  ModelsPage.Add('small');
  ModelsPage.Add('tiny');
  ModelsPage.Add('Skip model download for now');
  ModelsPage.Values[2] := True;

  ResourcesPage := CreateInputDirPage(
    ModelsPage.ID,
    'Resource Folders',
    'Choose shared resource folders',
    'Models and local help docs are stored separately from the program directory.',
    False,
    ''
  );
  ResourcesPage.Add('Models directory');
  ResourcesPage.Add('Docs directory');
  UpdateResourceDefaults;

  DownloadPage := CreateOutputMsgPage(
    ResourcesPage.ID,
    'Install Summary',
    'Review every system change before installation continues.',
    ''
  );
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectDir then begin
    RefreshSelectedInstallScope;
    if not HasCommandLineDirOverride then
      ApplyDefaultInstallDir;
    UpdateResourceDefaults;
  end;

  if CurPageID = DownloadPage.ID then begin
    SelectedModelsDir := ResourcesPage.Values[0];
    SelectedDocsDir := ResourcesPage.Values[1];
    UpdateInstallSummary;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  DownloadError: String;
begin
  Result := True;

  if CurPageID = wpSelectComponents then begin
    if (not WizardIsComponentSelected('gui')) and (not WizardIsComponentSelected('cli')) then begin
      MsgBox('Select at least one of GUI or CLI.', mbError, MB_OK);
      Result := False;
      exit;
    end;
  end;

  if CurPageID = wpSelectDir then begin
    if not ValidateManagedDirectory(WizardForm.DirEdit.Text, 'installation directory') then begin
      Result := False;
      exit;
    end;
  end;

  if CurPageID = ModelsPage.ID then begin
    if ModelsPage.Values[2] then begin
      ModelsPage.Values[0] := False;
      ModelsPage.Values[1] := False;
    end;
  end;

  if CurPageID = ResourcesPage.ID then begin
    if (not ModelsPage.Values[2]) and (not ValidateManagedDirectory(ResourcesPage.Values[0], 'models directory')) then begin
      Result := False;
      exit;
    end;
    if WizardIsComponentSelected('docs') and (not ValidateManagedDirectory(ResourcesPage.Values[1], 'docs directory')) then begin
      Result := False;
      exit;
    end;
  end;

  if IsOnlineBuild and (CurPageID = wpReady) then begin
    if not DownloadOnlinePayloads(DownloadError) then begin
      SuppressibleMsgBox(DownloadError, mbCriticalError, MB_OK, IDOK);
      Result := False;
      exit;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  Log('PrepareToInstall invoked. IsOnlineBuild=' + IntToStr(Integer(IsOnlineBuild)));
  if IsOnlineBuild then begin
    if not DownloadOnlinePayloads(Result) then
      exit;
    if not PrepareOnlinePayloads(Result) then
      exit;
  end;
end;

function GetDocsIndexPath(Param: String): String;
begin
  if FileExists(ExpandConstant('{app}\docs\index.html')) then
    Result := ExpandConstant('{app}\docs\index.html')
  else
    Result := ExpandConstant('{app}\docs\model-guide.html');
end;

function HasDocsIndex: Boolean;
begin
  Result := FileExists(GetDocsIndexPath(''));
end;

function EnsurePathValue(ExistingValue, Segment: String): String;
var
  SearchValue: String;
begin
  SearchValue := ';' + Lowercase(ExistingValue) + ';';
  if Pos(';' + Lowercase(Segment) + ';', SearchValue) > 0 then
    Result := ExistingValue
  else if ExistingValue = '' then
    Result := Segment
  else
    Result := ExistingValue + ';' + Segment;
end;

function QueryExistingPath(RootKey: Integer; const Subkey: String): String;
begin
  if not RegQueryStringValue(RootKey, Subkey, 'Path', Result) then
    Result := '';
end;

function GetCurrentUserPathBackup(Value: String): String;
begin
  Result := QueryExistingPath(HKCU, 'Environment');
end;

function GetCurrentSystemPathBackup(Value: String): String;
begin
  Result := QueryExistingPath(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment');
end;

function GetUpdatedUserPath(Value: String): String;
begin
  Result := EnsurePathValue(
    QueryExistingPath(HKCU, 'Environment'),
    ExpandConstant('{app}\CLI')
  );
end;

function GetUpdatedSystemPath(Value: String): String;
begin
  Result := EnsurePathValue(
    QueryExistingPath(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
    ExpandConstant('{app}\CLI')
  );
end;

function RemovePathSegment(ExistingValue, Segment: String): String;
var
  Remaining: String;
  Item: String;
  DelimiterPos: Integer;
begin
  Remaining := ExistingValue;
  Result := '';

  while Remaining <> '' do begin
    DelimiterPos := Pos(';', Remaining);
    if DelimiterPos = 0 then begin
      Item := Remaining;
      Remaining := '';
    end else begin
      Item := Copy(Remaining, 1, DelimiterPos - 1);
      Delete(Remaining, 1, DelimiterPos);
    end;

    if CompareText(Trim(Item), Segment) <> 0 then begin
      if Result <> '' then
        Result := Result + ';';
      Result := Result + Item;
    end;
  end;
end;

procedure RemovePathSegmentFromRegistry(RootKey: Integer; const Subkey, Segment: String);
var
  ExistingValue: String;
  UpdatedValue: String;
begin
  ExistingValue := QueryExistingPath(RootKey, Subkey);
  UpdatedValue := RemovePathSegment(ExistingValue, Segment);
  if ExistingValue = UpdatedValue then
    exit;

  Log('Updating PATH during uninstall for ' + Subkey + ': removing ' + Segment);
  if UpdatedValue = '' then
    RegDeleteValue(RootKey, Subkey, 'Path')
  else
    RegWriteExpandStringValue(RootKey, Subkey, 'Path', UpdatedValue);
end;

function IsSafeManagedDeleteTarget(DirPath, MarkerName: String): Boolean;
begin
  Result := (DirPath <> '') and (not IsUnsafeDirectoryTarget(DirPath)) and DirExists(DirPath) and HasDirectoryMarker(DirPath, MarkerName);
end;

procedure SafeDeleteManagedDir(DirPath, MarkerName: String);
begin
  if not IsSafeManagedDeleteTarget(DirPath, MarkerName) then begin
    if DirPath <> '' then
      Log('Skipping recursive delete for unmanaged or unsafe path: ' + DirPath);
    exit;
  end;

  Log('Deleting managed directory: ' + DirPath);
  DelTree(DirPath, True, True, True);
end;

function RunHiddenExe(FileName, Params, WorkingDir: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(
    FileName,
    Params,
    WorkingDir,
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) and (ResultCode = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  HelperExe: String;
  ComponentArgs: String;
  SelectedModels: String;
begin
  if CurStep = ssInstall then begin
    EnsureDirectoryExists(ExpandConstant('{app}'));
    EnsureDirectoryMarker(ExpandConstant('{app}'), InstallRootMarkerName);
    SaveInstallerStateValue(ModelsDirStateFileName, ResourcesPage.Values[0]);
    SaveInstallerStateValue(DocsDirStateFileName, ResourcesPage.Values[1]);
    if ShouldAddToPathCurrentUser then
      SaveInstallerStateValue(UserPathBackupFileName, QueryExistingPath(HKCU, 'Environment'));
    if ShouldAddToPathAllUsers then
      SaveInstallerStateValue(SystemPathBackupFileName, QueryExistingPath(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'));
    exit;
  end;

  if CurStep <> ssPostInstall then
    exit;

  if ModelsPage.Values[2] then
    Log('Model download skipped by installer selection.')
  else
    EnsureDirectoryMarker(SelectedModelsDir, ManagedDirMarkerName);

  if WizardIsComponentSelected('docs') then begin
    if DirExists(ExpandConstant('{app}\docs')) then begin
      EnsureDirectoryMarker(SelectedDocsDir, ManagedDirMarkerName);
      Log('Staging docs from ' + ExpandConstant('{app}\docs') + ' to ' + SelectedDocsDir);
      if not DirExists(SelectedDocsDir) then
        ForceDirectories(SelectedDocsDir);
      if not RunHiddenExe(
        ExpandConstant('{cmd}'),
        '/c xcopy /E /I /Y "' + ExpandConstant('{app}\docs') + '" "' + SelectedDocsDir + '"',
        ExpandConstant('{app}')
      ) then
        MsgBox('FlowScribe could not stage local docs into the shared docs folder.', mbError, MB_OK);
    end;
  end;

  HelperExe := ExpandConstant('{app}\CLI\FlowScribe.exe');
  if not FileExists(HelperExe) then begin
    MsgBox('FlowScribe installer helper was not found in the CLI package. Model setup will be skipped.', mbError, MB_OK);
    exit;
  end;

  ComponentArgs := '';
  if WizardIsComponentSelected('gui') then
    ComponentArgs := ComponentArgs + ' --component gui';
  if WizardIsComponentSelected('cli') then
    ComponentArgs := ComponentArgs + ' --component cli';
  if WizardIsComponentSelected('docs') then
    ComponentArgs := ComponentArgs + ' --component docs';

  Log('Running installer helper to write install-config.json for scope ' + SelectedInstallScope);
  if not RunHiddenExe(
    HelperExe,
    ' install write-config --scope ' + SelectedInstallScope +
    ' --models-dir "' + SelectedModelsDir + '"' +
    ' --docs-dir "' + SelectedDocsDir + '"' +
    ComponentArgs,
    ExpandConstant('{app}\CLI')
  ) then
    MsgBox('FlowScribe could not write install-config.json. Managed resources may not work correctly.', mbError, MB_OK);

  SelectedModels := BuildModelList;
  if SelectedModels <> '' then begin
    if Pos('small', SelectedModels) > 0 then begin
      Log('Downloading model during setup: small to ' + SelectedModelsDir);
      if not RunHiddenExe(
        HelperExe,
        ' model download small --models-dir "' + SelectedModelsDir + '"',
        ExpandConstant('{app}\CLI')
      ) then
        MsgBox('FlowScribe could not download the small model during setup.', mbError, MB_OK);
    end;
    if Pos('tiny', SelectedModels) > 0 then begin
      Log('Downloading model during setup: tiny to ' + SelectedModelsDir);
      if not RunHiddenExe(
        HelperExe,
        ' model download tiny --models-dir "' + SelectedModelsDir + '"',
        ExpandConstant('{app}\CLI')
      ) then
        MsgBox('FlowScribe could not download the tiny model during setup.', mbError, MB_OK);
    end;
  end else begin
    MsgBox(
      'No model was downloaded during installation. FlowScribe will not auto-download one on first use.' + #13#10 +
      'Open Model Center after launch to download the recommended `small` model.',
      mbInformation,
      MB_OK
    );
  end;
end;

procedure InitializeUninstallProgressForm;
begin
  RemoveProgramFiles := MsgBox(
    'Also remove any remaining files inside the installation directory after uninstall finishes?' + #13#10 +
    'This only runs when the folder still looks like a dedicated FlowScribe install root.',
    mbConfirmation,
    MB_YESNO or MB_DEFBUTTON2
  ) = IDYES;
  RemoveSharedResources := MsgBox(
    'Also remove downloaded models and local help docs from managed FlowScribe resource folders?',
    mbConfirmation,
    MB_YESNO or MB_DEFBUTTON2
  ) = IDYES;
  RemoveUserData := MsgBox(
    'Also remove this Windows user''s FlowScribe settings, logs, queue, and transcript library data?' + #13#10 +
    'Current review patch keeps this conservative and does not recursively wipe broad AppData roots without a dedicated data manifest.',
    mbConfirmation,
    MB_YESNO or MB_DEFBUTTON2
  ) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserRoot: String;
  SharedRoot: String;
  ModelsDir: String;
  DocsDir: String;
begin
  if CurUninstallStep = usUninstall then begin
    RemovePathSegmentFromRegistry(HKCU, 'Environment', ExpandConstant('{app}\CLI'));
    RemovePathSegmentFromRegistry(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', ExpandConstant('{app}\CLI'));

    ModelsDir := Trim(LoadInstallerStateValue(ModelsDirStateFileName));
    DocsDir := Trim(LoadInstallerStateValue(DocsDirStateFileName));

    if RemoveSharedResources then begin
      SafeDeleteManagedDir(ModelsDir, ManagedDirMarkerName);
      SafeDeleteManagedDir(DocsDir, ManagedDirMarkerName);
    end;

    if RemoveUserData then
      Log('User-data removal was requested, but broad AppData root deletion is disabled until FlowScribe provides a dedicated uninstall manifest.');
    exit;
  end;

  if CurUninstallStep = usPostUninstall then begin
    if RemoveProgramFiles then
      SafeDeleteManagedDir(ExpandConstant('{app}'), InstallRootMarkerName);
  end;
end;
