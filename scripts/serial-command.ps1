param(
    [Parameter(Mandatory)]
    [string]$Command,
    [string]$Port,
    [int]$Baud,
    [ValidateRange(1, 30)]
    [int]$ReadSeconds = 2
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
$serial.NewLine = "`r`n"
$serial.ReadTimeout = 100
$serial.DtrEnable = $false
$serial.RtsEnable = $false

try {
    $serial.Open()
    $serial.WriteLine($Command)
    $deadline = [DateTime]::UtcNow.AddSeconds($ReadSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
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

