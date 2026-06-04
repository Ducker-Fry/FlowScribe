#include "FlowScribe-common.iss"

[Setup]
AppId={{1A40D5B8-3C07-4BE0-B92A-A807F4B9F001}
DefaultDirName={localappdata}\Programs\FlowScribe
OutputBaseFilename=FlowScribeSetup-offline-x64

[Files]
Source: "..\dist\FlowScribe\*"; DestDir: "{app}\CLI"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: cli helper
Source: "..\dist\FlowScribeGUI\*"; DestDir: "{app}\GUI"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: gui
Source: "..\build\docs-site\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: docs
