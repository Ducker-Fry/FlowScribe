#ifndef OnlineVersion
#define OnlineVersion "v0.3.3"
#endif
#define BuildFlavor "online"
#ifndef OnlineCliZipName
#define OnlineCliZipName "FlowScribe-0.3.3-windows-x64.zip"
#endif
#ifndef OnlineGuiZipName
#define OnlineGuiZipName "FlowScribeGUI-0.3.3-windows-x64.zip"
#endif
#ifndef OnlineCliUrl
#define OnlineCliUrl "https://github.com/Ducker-Fry/FlowScribe/releases/download/" + OnlineVersion + "/" + OnlineCliZipName
#endif
#ifndef OnlineGuiUrl
#define OnlineGuiUrl "https://github.com/Ducker-Fry/FlowScribe/releases/download/" + OnlineVersion + "/" + OnlineGuiZipName
#endif
#ifndef OnlineCliSha256
#error OnlineCliSha256 must be provided via ISCC /DOnlineCliSha256=...
#endif
#ifndef OnlineGuiSha256
#error OnlineGuiSha256 must be provided via ISCC /DOnlineGuiSha256=...
#endif

#include "FlowScribe-common.iss"

[Setup]
AppId={{7B0E9E68-3E86-4984-A2F1-7B9F1AF6B001}
DefaultDirName={code:GetSetupDefaultDir}
OutputBaseFilename=FlowScribeSetup-online-x64
PrivilegesRequired=admin
ArchiveExtraction=full

[Files]
Source: "{tmp}\flowscribe-online-staging\FlowScribe\*"; DestDir: "{app}\CLI"; Flags: external ignoreversion recursesubdirs createallsubdirs; Components: cli helper
Source: "{tmp}\flowscribe-online-staging\FlowScribeGUI\*"; DestDir: "{app}\GUI"; Flags: external ignoreversion recursesubdirs createallsubdirs; Components: gui
Source: "..\build\docs-site\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: docs
