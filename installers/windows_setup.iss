; =========================================
; Viboy Color - Inno Setup Script
; =========================================
; Script de configuración para crear un instalador de Windows
; Requiere: Inno Setup (https://jrsoftware.org/isinfo.php)
;
; Uso:
;   1. Compilar el .exe con tools/build_release.py
;   2. Abrir este archivo en Inno Setup Compiler
;   3. Compilar el instalador
; =========================================

#define AppName "Viboy Color"
#define AppVersion "0.0.1"
#define AppPublisher "Viboy Color Project"
#define AppURL "https://github.com/tu-usuario/viboy-color"
#define AppExeName "ViboyColor.exe"

[Setup]
; Información básica
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=
OutputDir=..\release
OutputBaseFilename=ViboyColor-Setup-{#AppVersion}
SetupIconFile=..\assets\viboycolor-icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Ejecutable principal
Source: "..\release\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Assets (si se incluyen por separado)
; Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Código personalizado (opcional)
// Puedes añadir verificaciones de dependencias, configuraciones, etc.

