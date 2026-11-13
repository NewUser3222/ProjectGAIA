Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = oWS.SpecialFolders("Desktop") & "\GAIA.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
	oLink.TargetPath = "E:\ProjectGAIA\experiments\gaia_py_sim\Launch_GAIA.bat"
	oLink.IconLocation = "E:\ProjectGAIA\experiments\gaia_py_sim\assets\gaia_icon_hd.ico"
	oLink.Description = "Launch GAIA: Emergent Civilization"
	oLink.WorkingDirectory = "E:\ProjectGAIA\experiments\gaia_py_sim"
oLink.Save
WScript.Echo "Shortcut created on Desktop."
