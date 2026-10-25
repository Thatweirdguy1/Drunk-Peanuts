# FreeConvert: Windows installation and signing

The Windows build is a bundled desktop executable with Qt, VLC and conversion runtimes. Users do not need Python or a terminal. Python remains the implementation language; packaging does not translate the application into C++.

`installer.iss` creates a per-user installer. It installs to `%LOCALAPPDATA%\Programs\FreeConvert`, adds Desktop and Start menu shortcuts, includes an uninstaller in Installed apps, and registers WatchIT for supported audio/video extensions under Open with and Default apps. It does not modify `UserChoice`, change an existing default player, or require administrator rights. Media launch uses a quoted `"LocalFileConverter.exe" --play "%1"` command and queues the file until the playback engine is ready.

The **Templates** menu creates an editable document in a location you choose and opens it in a separate workspace, preserving any existing unsaved editor. It refuses to overwrite an existing file. The installer also includes the starters in `_internal/assets/templates` and a Start menu shortcut to that folder. Templates cover reports, letters, meeting notes, budget, task tracking, slides, contacts, equations, drawing and screenplay. Shift+Enter converts the current queue; Shift-drop opens the existing quick-format menu.

## Is a Windows signature required?

A signature is not what creates Desktop shortcuts or Open with registration. An unsigned Win32 executable can run locally, subject to the computer's security policy. Public distribution should use trusted Authenticode signing; unsigned downloads may be blocked or show SmartScreen warnings. This build is **unsigned**. No certificate was purchased and no trust/security settings were changed.

Options, checked against Microsoft's documentation on 25 October 2026:

- **Microsoft Store, MSIX route:** Microsoft re-signs the certified package, so you do not purchase a code-signing certificate for that route. A Store listing for an EXE/MSI installer still requires your own trusted signature.
- **Qualifying open-source project:** apply to SignPath Foundation for free managed signing. Acceptance is not automatic.
- **Direct downloads:** obtain a public code-signing certificate/service from a trusted CA that accepts your publisher identity and country. Validate eligibility before paying; organization validation and a hardware token or cloud HSM may be required. Microsoft's Azure Artifact Signing currently limits individuals to the USA/Canada, so it is not currently an option for an individual publisher based in India.
- Self-signed certificates are for controlled development/testing, not public trust. EV signing does not guarantee immediate SmartScreen reputation.

With a valid certificate/service configured, sign **your built executable first**, compile the installer, then sign the installer; timestamp both with SHA-256 and verify their Authenticode signatures. Keep signing credentials outside the repository. Example for a certificate already available in the Windows certificate store:

```powershell
signtool sign /sha1 YOUR_CERT_THUMBPRINT /fd SHA256 /tr YOUR_CA_RFC3161_TIMESTAMP_URL /td SHA256 dist\ui-016\LocalFileConverter\LocalFileConverter.exe
# Compile installer.iss after signing the app, then sign the resulting setup executable.
signtool verify /pa /v dist\FreeConvert-0.16.0-Setup.exe
```

Sources:

- [Microsoft: code signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [Microsoft: SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [Microsoft: Open with registration](https://learn.microsoft.com/en-us/windows/win32/shell/how-to-include-an-application-on-the-open-with-dialog-box)
- [SignPath Foundation](https://signpath.org/)

## Reference-app inspection

Live Word, LibreOffice and VLC windows were inspected through Computer Use. The installed Word, LibreOffice and libVLC SHA-256 hashes still match the previously collected REA Rizin imports and Ghidra overview. A fresh Rizin inspection of VLC's executable shows `CommandLineToArgvW` and shell imports; this is static evidence of command-line handling, not proof of a particular application behavior. The useful design patterns are compact toolbars, grouped actions, ordinary document starters and native shell registration. No Microsoft/LibreOffice/VLC proprietary code or artwork was copied.

JADX, Apktool and ADB target Android APKs/devices; the inspected applications are Windows PE binaries. They were not installed or used for this native Windows task.
