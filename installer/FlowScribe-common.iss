#define MyAppName "FlowScribe"
#define MyAppVersion "0.3.3"
#define MyAppPublisher "FlowScribe contributors"
#define MyAppURL "https://github.com/Ducker-Fry/FlowScribe"

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
ChangesEnvironment=yes
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
Name: "autostart"; Description: "Start FlowScribe GUI when I sign in"; GroupDescription: "Startup:"; Components: gui
Name: "addtopath"; Description: "Add FlowScribe CLI to PATH"; GroupDescription: "Command line:"; Components: cli; Flags: checkedonce
Name: "jsoncontext"; Description: "Add JSON right-click menu entry"; GroupDescription: "File integration:"; Components: gui; Flags: checkedonce

[Icons]
Name: "{group}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui
Name: "{group}\FlowScribe CLI"; Filename: "{app}\CLI\FlowScribe.exe"; Components: cli
Name: "{group}\FlowScribe Help"; Filename: "{code:GetDocsIndexPath}"; Components: docs; Check: HasDocsIndex
Name: "{group}\Uninstall FlowScribe"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui; Check: ShouldCreateDesktopShortcut
Name: "{userstartup}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui; Check: ShouldEnableAutoStartCurrentUser
Name: "{commonstartup}\FlowScribe"; Filename: "{app}\GUI\FlowScribeGUI.exe"; Components: gui; Check: ShouldEnableAutoStartAllUsers

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{code:GetUpdatedUserPath}"; Components: cli; Check: ShouldAddToPathCurrentUser; Flags: preservestringtype
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{code:GetUpdatedSystemPath}"; Components: cli; Check: ShouldAddToPathAllUsers; Flags: preservestringtype
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open"; ValueType: string; ValueName: ""; ValueData: "Use FlowScribe to open transcript"; Components: gui; Check: ShouldRegisterJsonContextCurrentUser
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\GUI\FlowScribeGUI.exe"" ""%1"""; Components: gui; Check: ShouldRegisterJsonContextCurrentUser
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open"; ValueType: string; ValueName: ""; ValueData: "Use FlowScribe to open transcript"; Components: gui; Check: ShouldRegisterJsonContextAllUsers
Root: HKLM; Subkey: "Software\Classes\SystemFileAssociations\.json\shell\FlowScribe.Open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\GUI\FlowScribeGUI.exe"" ""%1"""; Components: gui; Check: ShouldRegisterJsonContextAllUsers

[Run]
Filename: "{app}\GUI\FlowScribeGUI.exe"; Description: "Launch FlowScribe"; Flags: postinstall nowait skipifsilent; Components: gui

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  ShortcutsPage: TInputOptionWizardPage;
  FileAssocPage: TInputOptionWizardPage;
  ModelsPage: TInputOptionWizardPage;
  ResourcesPage: TInputDirWizardPage;
  DownloadPage: TOutputMsgWizardPage;
  UninstallOptionsPage: TInputOptionWizardPage;
  SelectedInstallScope: String;
  SelectedModelsDir: String;
  SelectedDocsDir: String;
  RemoveProgramFiles: Boolean;
  RemoveSharedResources: Boolean;
  RemoveUserData: Boolean;

function IsOfflineBuild: Boolean;
begin
  Result := ExpandConstant('{#SetupSetting("OutputBaseFilename")}') = 'FlowScribeSetup-offline-x64';
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
  Result := WizardIsComponentSelected('cli') and IsCurrentUserInstall;
end;

function ShouldAddToPathAllUsers: Boolean;
begin
  Result := WizardIsComponentSelected('cli') and IsAllUsersInstall;
end;

function ShouldRegisterJsonContextCurrentUser: Boolean;
begin
  Result := WizardIsComponentSelected('gui') and FileAssocPage.Values[0] and IsCurrentUserInstall;
end;

function ShouldRegisterJsonContextAllUsers: Boolean;
begin
  Result := WizardIsComponentSelected('gui') and FileAssocPage.Values[0] and IsAllUsersInstall;
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

procedure ApplyDefaultInstallDir;
begin
  RefreshSelectedInstallScope;
  if HasCommandLineDirOverride then
    exit;

  if IsCurrentUserInstall then
    WizardForm.DirEdit.Text := ExpandConstant('{localappdata}\Programs\FlowScribe')
  else
    WizardForm.DirEdit.Text := ExpandConstant('{autopf}\FlowScribe');
end;

procedure InitializeWizard;
begin
  RefreshSelectedInstallScope;
  ApplyDefaultInstallDir;

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
    'FlowScribe will add only a right-click action for transcript JSON files. It will not replace the default JSON app.',
    False,
    False
  );
  FileAssocPage.Add('Add "Use FlowScribe to open transcript" to .json right-click menu');
  FileAssocPage.Values[0] := True;

  ModelsPage := CreateInputOptionPage(
    FileAssocPage.ID,
    'Model Selection',
    'Choose models to download during installation',
    'Recommended: install small now to avoid long first-run waits. Paraformer and native-engine are available later from Model Center.',
    False,
    False
  );
  ModelsPage.Add('small (Recommended)');
  ModelsPage.Add('tiny');
  ModelsPage.Add('Skip model download for now');
  ModelsPage.Values[0] := True;

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
    'FlowScribe will install selected components first, then download any selected models.',
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
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = wpSelectComponents then begin
    if (not WizardIsComponentSelected('gui')) and (not WizardIsComponentSelected('cli')) then begin
      MsgBox('Select at least one of GUI or CLI.', mbError, MB_OK);
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

function GetUpdatedUserPath(Value: String): String;
begin
  Result := EnsurePathValue(Value, ExpandConstant('{app}\CLI'));
end;

function GetUpdatedSystemPath(Value: String): String;
begin
  Result := EnsurePathValue(Value, ExpandConstant('{app}\CLI'));
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
  if CurStep <> ssPostInstall then
    exit;

  if WizardIsComponentSelected('docs') then begin
    if DirExists(ExpandConstant('{app}\docs')) then begin
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
      if not RunHiddenExe(
        HelperExe,
        ' model download small --models-dir "' + SelectedModelsDir + '"',
        ExpandConstant('{app}\CLI')
      ) then
        MsgBox('FlowScribe could not download the small model during setup.', mbError, MB_OK);
    end;
    if Pos('tiny', SelectedModels) > 0 then begin
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
  RemoveProgramFiles := True;
  RemoveSharedResources := MsgBox(
    'Also remove downloaded models, model cache, and local help docs?',
    mbConfirmation,
    MB_YESNO
  ) = IDYES;
  RemoveUserData := MsgBox(
    'Also remove this Windows user''s FlowScribe settings, logs, queue, and transcript library data?',
    mbConfirmation,
    MB_YESNO
  ) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserRoot: String;
  SharedRoot: String;
begin
  if CurUninstallStep <> usUninstall then
    exit;

  if RemoveSharedResources then begin
    SharedRoot := ExpandConstant('{commonappdata}\FlowScribe');
    if DirExists(SharedRoot) then
      DelTree(SharedRoot, True, True, True);
    SharedRoot := ExpandConstant('{localappdata}\FlowScribe');
    if DirExists(SharedRoot) then
      DelTree(SharedRoot, True, True, True);
  end;

  if RemoveUserData then begin
    UserRoot := ExpandConstant('{localappdata}\FlowScribe');
    if DirExists(UserRoot) then
      DelTree(UserRoot, True, True, True);
    UserRoot := ExpandConstant('{userappdata}\FlowScribe');
    if DirExists(UserRoot) then
      DelTree(UserRoot, True, True, True);
  end;
end;
