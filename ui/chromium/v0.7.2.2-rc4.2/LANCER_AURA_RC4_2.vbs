Option Explicit
Dim sh, fso, base, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = Chr(34) & fso.BuildPath(fso.GetSpecialFolder(0), "System32\cmd.exe") & Chr(34) & " /d /c " & Chr(34) & base & "\LANCER_AURA_RC4_2.bat" & Chr(34)
sh.Run cmd, 0, False
