param([switch]$UseLocalBuild, [switch]$AllowDtePlaceholdersForLocalBuild)
& "$PSScriptRoot\stop.ps1" -UseLocalBuild:$UseLocalBuild -AllowDtePlaceholdersForLocalBuild:$AllowDtePlaceholdersForLocalBuild
& "$PSScriptRoot\start.ps1" -UseLocalBuild:$UseLocalBuild -AllowDtePlaceholdersForLocalBuild:$AllowDtePlaceholdersForLocalBuild
