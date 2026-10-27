Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"
. "$PSScriptRoot\env.ps1"

$config = Get-HuangshanProjectConfig
$projectDirectory = Join-Path (Get-HuangshanRepoRoot) 'project'

Push-Location -LiteralPath $projectDirectory
try {
    & sdk.py menuconfig "--board=$($config.Board)"
    if ($LASTEXITCODE -ne 0) {
        throw "menuconfig failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

