; Offline build — stub defines so FlowScribe-common.iss compiles.
; The [Code] section references these via {#...} and online code paths
; guard themselves via IsOnlineBuild(), but the preprocessor still needs
; the symbols to exist.
#define BuildFlavor "offline"
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

#include "FlowScribe-common.iss"

[Setup]
AppId={{1A40D5B8-3C07-4BE0-B92A-A807F4B9F001}
DefaultDirName={code:GetSetupDefaultDir}
OutputBaseFilename=FlowScribeSetup-offline-x64

[Files]
Source: "..\dist\FlowScribe\*"; DestDir: "{app}\CLI"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: cli helper
Source: "..\dist\FlowScribeGUI\*"; DestDir: "{app}\GUI"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: gui
Source: "..\build\docs-site\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: docs
