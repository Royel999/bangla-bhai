Unicode true
!include "MUI2.nsh"
!define APPN "The Royal Bengal Tiger"
!define EXE "The Royal Bengal Tiger.exe"
Name "${APPN}"
OutFile "..\dist\RoyalBengalTiger-Setup-1.0.0.exe"
InstallDir "$LOCALAPPDATA\Programs\RoyalBengalTiger"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Section
  nsExec::Exec 'taskkill /F /IM "${EXE}"'
  SetOutPath "$INSTDIR"
  File /r "..\dist\win-unpacked\*.*"
  File "icon.ico"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\${APPN}"
  CreateShortcut "$SMPROGRAMS\${APPN}\${APPN}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\icon.ico"
  CreateShortcut "$DESKTOP\${APPN}.lnk" "$INSTDIR\${EXE}" "" "$INSTDIR\icon.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "RoyalBengalTiger" '"$INSTDIR\${EXE}" --hidden'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RoyalBengalTiger" "DisplayName" "${APPN}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RoyalBengalTiger" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RoyalBengalTiger" "DisplayIcon" "$INSTDIR\icon.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RoyalBengalTiger" "DisplayVersion" "1.0.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RoyalBengalTiger" "Publisher" "S.K Shofikul Islam Badol"
SectionEnd
Section "Uninstall"
  nsExec::Exec 'taskkill /F /IM "${EXE}"'
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "RoyalBengalTiger"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "org.dpdns.banglabhai.rbt"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RoyalBengalTiger"
  Delete "$DESKTOP\${APPN}.lnk"
  RMDir /r "$SMPROGRAMS\${APPN}"
  RMDir /r "$INSTDIR"
SectionEnd
