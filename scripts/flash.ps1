[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param([string]$Port)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"
. "$PSScriptRoot\env.ps1"

$config = Get-HuangshanProjectConfig
$resolvedPort = Resolve-HuangshanSerialPort -Port $Port
$buildDirectory = Join-Path (Get-HuangshanRepoRoot) "project\build_$($config.Board)_$($config.Cpu)"

$images = @(
    @{ Path = Join-Path $buildDirectory 'bootloader\bootloader.bin'; Address = '0x12010000' },
    @{ Path = Join-Path $buildDirectory 'main.bin';                  Address = '0x12020000' },
    @{ Path = Join-Path $buildDirectory 'ftab\ftab.bin';            Address = '0x12000000' }
)

foreach ($image in $images) {
    if (-not (Test-Path -LiteralPath $image.Path -PathType Leaf)) {
        throw "Firmware image not found: $($image.Path). Run scripts\build.ps1 first."
    }
}

$description = "Flash $($config.Board) firmware to $resolvedPort"
if ($PSCmdlet.ShouldProcess($resolvedPort, $description)) {
    $arguments = @('-p', $resolvedPort, '-c', $config.Chip, '-m', 'nor', 'write_flash')
    $arguments += $images | ForEach-Object { "$($_.Path)@$($_.Address)" }
    & sftool @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Flashing failed with exit code $LASTEXITCODE."
    }
}

