' TD Radar hidden task launcher.
' Resolves the repo/install folder, pins data to that folder's data directory,
' and starts the poll without a console window.
Option Explicit
Dim fso, sh, base, exe, data, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

base = fso.GetParentFolderName(WScript.ScriptFullName)
exe = base & "\dist\tdradar\tdradar.exe"
If Not fso.FileExists(exe) Then exe = base & "\tdradar.exe"

data = base & "\data"
If Not fso.FolderExists(data) Then fso.CreateFolder data

sh.Environment("PROCESS")("TD_RADAR_DATA") = data
cmd = """" & exe & """ canvas poll --once --download --process"
sh.Run cmd, 0, False
