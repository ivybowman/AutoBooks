$DownloadUrl = "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8/npp.8.0.Installer.exe"

$SaveTo = "C:\temp\notepad++_setup.exe"

Invoke-WebRequest -uri $DownloadUrl -OutFile $SaveTo