param(
    [string]$Port,
    [int]$Baud
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$config = Get-HuangshanProjectConfig
if (-not $Baud) {
    $Baud = $config.SerialBaud
}
$resolvedPort = Resolve-HuangshanSerialPort -Port $Port
$serial = [System.IO.Ports.SerialPort]::new($resolvedPort, $Baud, 'None', 8, 'One')
$serial.Encoding = [System.Text.Encoding]::UTF8
$serial.DtrEnable = $false
$serial.RtsEnable = $false

Write-Host "Opening $resolvedPort at $Baud baud. Press Ctrl+C to stop."
try {
    $serial.Open()
    while ($true) {
        $text = $serial.ReadExisting()
        if ($text) {
            Write-Host -NoNewline $text
        }
        Start-Sleep -Milliseconds 50
    }
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
}

