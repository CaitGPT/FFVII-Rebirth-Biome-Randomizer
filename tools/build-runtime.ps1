param(
    [Parameter(Mandatory=$true)][string]$Ue4ssSource,
    [Parameter(Mandatory=$true)][string]$UePseudoSource,
    [Parameter(Mandatory=$true)][string]$ImGuiSource,
    [Parameter(Mandatory=$true)][string]$ImGuiTextEditSource,
    [Parameter(Mandatory=$true)][string]$ZydisSource,
    [Parameter(Mandatory=$true)][string]$Ue4ssImportLib,
    [string]$CMake='cmake',
    [string]$Python='python',
    [string]$BuildDirectory=(Join-Path $PSScriptRoot '..\build\runtime-portable')
)
$ErrorActionPreference='Stop'
$pins=@(
    @($Ue4ssSource,'d935b5b23bac03b65c14ae38382b02007204cc2e'),
    @($UePseudoSource,'d09b7218bfe7392adeffb500fdeee0b42ca1cd27'),
    @($ImGuiSource,'81160fee56027226bc80b48e196d0332f5541a8c'),
    @($ImGuiTextEditSource,'af7821926251feca84e35f8fa83eee84dae90424'),
    @($ZydisSource,'569320ad3c4856da13b9dbf1f0d9e20bda63870e')
)
foreach($pin in $pins){
    $actual=& git -C $pin[0] rev-parse HEAD
    if($LASTEXITCODE -ne 0 -or $actual -ne $pin[1]){throw "Dependency commit differs: $($pin[0])"}
    & git -C $pin[0] diff --quiet --ignore-submodules=all HEAD --
    if($LASTEXITCODE -ne 0){throw "Dependency has tracked changes: $($pin[0])"}
}
if(-not (Test-Path -LiteralPath $Ue4ssImportLib -PathType Leaf)){throw 'Missing matching UE4SS import library'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$BuildDirectory=[IO.Path]::GetFullPath($BuildDirectory)
$interface=Join-Path $BuildDirectory 'installed-interface'
& $Python (Join-Path $PSScriptRoot 'prepare-runtime-interface.py') $Ue4ssSource $interface
if($LASTEXITCODE -ne 0){throw 'Pinned interface preparation failed'}
& $CMake -S (Join-Path $repo 'runtime\Native') -B $BuildDirectory -G 'Visual Studio 17 2022' -A x64 `
    "-DINSTALLED_INTERFACE=$interface" "-DUE4SS_SOURCE=$Ue4ssSource" "-DUEPSEUDO_SOURCE=$UePseudoSource" `
    "-DIMGUI_SOURCE=$ImGuiSource" "-DIMGUI_TEXT_EDIT_SOURCE=$ImGuiTextEditSource" `
    "-DZYDIS_SOURCE=$ZydisSource" "-DUE4SS_IMPORT_LIB=$Ue4ssImportLib"
if($LASTEXITCODE -ne 0){throw 'Runtime configure failed'}
& $CMake --build $BuildDirectory --config Release --parallel 1 -- /nr:false
if($LASTEXITCODE -ne 0){throw 'Runtime build failed'}
& (Join-Path $BuildDirectory 'Release\RuntimeArgumentTests.exe')
if($LASTEXITCODE -ne 0){throw 'Native argument regression failed'}
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $BuildDirectory 'Release\main.dll')
