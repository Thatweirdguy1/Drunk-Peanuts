#ifndef AppVersion
  #define AppVersion "0.20.0"
#endif
#ifndef PackageDir
  #define PackageDir "dist\ui-020\LocalFileConverter"
#endif
[Setup]
AppId={{61E4A40A-4EB0-4C4F-8D5E-95FC31F7C825}
AppName=FreeConvert
AppVersion={#AppVersion}
AppPublisher=Prabhav Goel
AppPublisherURL=https://github.com/Thatweirdguy1/FreeConvert
DefaultDirName={localappdata}\Programs\FreeConvert
DefaultGroupName=FreeConvert
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\LocalFileConverter.exe
SetupIconFile=assets\app.ico
OutputDir=dist
OutputBaseFilename=FreeConvert-{#AppVersion}-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\FreeConvert"; Filename: "{app}\LocalFileConverter.exe"; WorkingDir: "{app}"; IconFilename: "{app}\LocalFileConverter.exe"
Name: "{userprograms}\FreeConvert\FreeConvert"; Filename: "{app}\LocalFileConverter.exe"; WorkingDir: "{app}"
Name: "{userprograms}\FreeConvert\Uninstall FreeConvert"; Filename: "{uninstallexe}"
Name: "{userprograms}\FreeConvert\Office templates"; Filename: "{app}\_internal\assets\templates"

[Run]
Filename: "{app}\LocalFileConverter.exe"; Parameters: "--register-windows"; Flags: runhidden waituntilterminated
Filename: "{app}\LocalFileConverter.exe"; Description: "Open FreeConvert"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\LocalFileConverter.exe"; Parameters: "--unregister-windows"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterFreeConvert"
