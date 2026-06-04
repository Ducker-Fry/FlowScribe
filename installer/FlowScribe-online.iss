#include "FlowScribe-common.iss"

[Setup]
AppId={{7B0E9E68-3E86-4984-A2F1-7B9F1AF6B001}
DefaultDirName={autopf}\FlowScribe
OutputBaseFilename=FlowScribeSetup-online-x64
PrivilegesRequired=admin

[Files]
; Placeholder v1 online layout:
; The setup stays small by shipping only the helper runtime plus docs.
; GUI/CLI payload download manifests can be added in a follow-up release.
Source: "..\dist\FlowScribe\*"; DestDir: "{app}\CLI"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: cli helper
Source: "..\dist\FlowScribeGUI\*"; DestDir: "{app}\GUI"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: gui
Source: "..\build\docs-site\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: docs
