param(
    [Parameter(Mandatory=$true)][string]$Ue4ssDll,
    [string]$OutputDirectory=(Join-Path $PSScriptRoot '..\build\loader-import'),
    [string]$Dumpbin='dumpbin',
    [string]$LibTool='lib'
)
$ErrorActionPreference='Stop'
$expected='3F5E8D934FE91FF26BE2CE3585CEF0940D3C73B40295ADC09FA6E7B62BC0018F'
if((Get-FileHash -LiteralPath $Ue4ssDll -Algorithm SHA256).Hash -ne $expected){throw 'Unreviewed UE4SS DLL; import ABI is not accepted'}
$listing=& $Dumpbin /nologo /exports $Ue4ssDll
if($LASTEXITCODE -ne 0){throw 'Could not read loader exports'}
$names=@($listing | ForEach-Object {
    if($_ -match '^\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]{8,16}\s+(\S+)'){ $matches[1] }
} | Sort-Object -Unique)
if($names.Count -lt 100){throw 'Unexpected loader export listing'}
$OutputDirectory=[IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$definition=Join-Path $OutputDirectory 'UE4SS.def'
$library=Join-Path $OutputDirectory 'UE4SS.lib'
[IO.File]::WriteAllLines($definition,@('LIBRARY UE4SS.dll','EXPORTS')+$names,[Text.UTF8Encoding]::new($false))
& $LibTool /nologo "/def:$definition" /machine:x64 "/out:$library"
if($LASTEXITCODE -ne 0){throw 'Import library generation failed'}
$manifest=@{loader_sha256=$expected;exports=$names.Count;definition_sha256=(Get-FileHash -LiteralPath $definition).Hash;library_sha256=(Get-FileHash -LiteralPath $library).Hash}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'manifest.json') -Encoding UTF8
$manifest | ConvertTo-Json
