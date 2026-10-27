Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$repoRoot = Get-HuangshanRepoRoot
$config = Get-HuangshanProjectConfig

Write-Host "Repository : $repoRoot"
Write-Host "Board      : $($config.Board)"
Write-Host "SDK lock   : $($config.Sdk.Version)"

try {
    . "$PSScriptRoot\env.ps1"
    Write-Host '[OK] SiFli-SDK environment activated.' -ForegroundColor Green
    foreach ($tool in @('python', 'scons', 'sftool', 'arm-none-eabi-gcc')) {
        $command = Get-Command $tool -ErrorAction Stop
        Write-Host "[OK] $tool -> $($command.Source)" -ForegroundColor Green
    }
}
catch {
    Write-Host "[FAIL] SDK environment: $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}

$ports = @(Get-HuangshanSerialPorts)
if ($ports.Count -eq 0) {
    Write-Warning 'No serial device detected. Connect the board USB-to-UART Type-C port with a data cable.'
}
else {
    Write-Host 'Detected serial ports:'
    $ports | Sort-Object Port | Format-Table Port, LikelyBoard, Description -AutoSize
}

Write-Host 'Manual power checks:' -ForegroundColor Cyan
Write-Host '  [ ] 30-pin header pins 5-6 are shorted (VBAT)'
Write-Host '  [ ] 30-pin header pins 7-8 are shorted (VSYS)'
Write-Host '  [ ] 30-pin header pins 11-12 are shorted (VCC_3V3)'
Write-Host '  [ ] USB cable supports data, not charge-only'

