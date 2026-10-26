#ifndef AppVersion
  #define AppVersion "0.22.0"
#endif
#ifndef PackageDir
  #define PackageDir "dist\ui-021\LocalFileConverter"
#endif
[Setup]
AppId={{61E4A40A-4EB0-4C4F-8D5E-95FC31F7C825}
AppName=Drunk Peanuts
AppVersion={#AppVersion}
AppPublisher=Prabhav Goel
AppPublisherURL=https://github.com/Thatweirdguy1/Drunk-Peanuts
DefaultDirName={localappdata}\Programs\DrunkPeanuts
DefaultGroupName=Drunk Peanuts
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\LocalFileConverter.exe
SetupIconFile=assets\app.ico
OutputDir=dist
OutputBaseFilename=DrunkPeanuts-{#AppVersion}-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Drunk Peanuts"; Filename: "{app}\LocalFileConverter.exe"; WorkingDir: "{app}"; IconFilename: "{app}\LocalFileConverter.exe"
Name: "{userprograms}\Drunk Peanuts\Drunk Peanuts"; Filename: "{app}\LocalFileConverter.exe"; WorkingDir: "{app}"
Name: "{userprograms}\Drunk Peanuts\Uninstall Drunk Peanuts"; Filename: "{uninstallexe}"
Name: "{userprograms}\Drunk Peanuts\Office templates"; Filename: "{app}\_internal\assets\templates"

[Run]
Filename: "{app}\LocalFileConverter.exe"; Parameters: "--register-windows"; Flags: runhidden waituntilterminated
Filename: "{app}\LocalFileConverter.exe"; Description: "Open Drunk Peanuts"; Flags: postinstall nowait skipifsilent

[InstallDelete]
Type: files; Name: "{autodesktop}\FreeConvert.lnk"
Type: files; Name: "{userprograms}\FreeConvert\FreeConvert.lnk"
Type: files; Name: "{userprograms}\FreeConvert\Uninstall FreeConvert.lnk"
Type: files; Name: "{userprograms}\FreeConvert\Office templates.lnk"

[UninstallRun]
Filename: "{app}\LocalFileConverter.exe"; Parameters: "--unregister-windows"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterDrunk Peanuts"
