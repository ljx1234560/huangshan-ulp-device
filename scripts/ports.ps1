param([switch]$Json)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$ports = @(Get-HuangshanSerialPorts)
if ($Json) {
    $ports | ConvertTo-Json -Depth 3
    exit 0
}

if ($ports.Count -eq 0) {
    Write-Warning 'No serial port is currently connected.'
    exit 1
}

$ports | Sort-Object Port | Format-Table Port, LikelyBoard, Description, Name -AutoSize

