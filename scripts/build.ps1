param(
    [ValidateRange(1, 64)]
    [int]$Jobs = [Math]::Min([Environment]::ProcessorCount, 16)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"
. "$PSScriptRoot\env.ps1"

$config = Get-HuangshanProjectConfig
$projectDirectory = Join-Path (Get-HuangshanRepoRoot) 'project'

Write-Host "Building $($config.Name) for $($config.Board) with $Jobs jobs..."
Push-Location -LiteralPath $projectDirectory
try {
    & scons "--board=$($config.Board)" "-j$Jobs"
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

