Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"
. "$PSScriptRoot\env.ps1"

$config = Get-HuangshanProjectConfig
$projectDirectory = Join-Path (Get-HuangshanRepoRoot) 'project'

Push-Location -LiteralPath $projectDirectory
try {
    & scons "--board=$($config.Board)" -c
    if ($LASTEXITCODE -ne 0) {
        throw "Clean failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

