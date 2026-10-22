; Inno Setup 6 script — build BanglaBhaiLink-Setup.exe for আব্বা's own PCs
; Compile on Windows after PyInstaller onedir output exists in dist\BanglaBhaiLink\
#define MyAppName "বাংলা ভাই · Royal Link"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "Royal Universe"
#define MyAppExeName "BanglaBhaiLink.exe"

[Setup]
AppId={{B8A1C4D2-BB43-4F0E-9C11-ROYALUNIVERSE01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\RoyalUniverse\BanglaBhaiLink
DefaultGroupName=Royal Universe
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=BanglaBhaiLink-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; Unsigned / self-signed OK for personal machines (SmartScreen → More info → Run anyway)

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Start with Windows (tray)"; GroupDescription: "Startup:"

[Files]
Source: "dist\BanglaBhaiLink\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Royal Link চালু করুন"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption :=
    'এই অ্যাপ শুধু মালিকের অনুমতিতে কাজ করে।'#13#10#13#10 +
    'প্রথমবার URL দেবেন, তারপর বাংলা ভাই অ্যাপে ডিভাইস অনুমোদন দিতে হবে।'#13#10 +
    'কোনো কাজ গোপনে হয় না।';
end;
