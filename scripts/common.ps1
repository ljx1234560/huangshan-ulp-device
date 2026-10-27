Set-StrictMode -Version Latest

function Get-HuangshanRepoRoot {
    return (Split-Path -Parent $PSScriptRoot)
}

function Get-HuangshanProjectConfig {
    $configPath = Join-Path (Get-HuangshanRepoRoot) 'config\project.psd1'
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw "Project configuration not found: $configPath"
    }
    return Import-PowerShellDataFile -LiteralPath $configPath
}

function Get-HuangshanSerialPorts {
    # SerialPort.GetPortNames() reflects newly attached ports immediately.  On
    # some Windows systems Win32_SerialPort lags behind plug-and-play state, so
    # use CIM only to enrich the authoritative .NET port list with USB details.
    try {
        $portNames = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object -Unique)
    }
    catch {
        throw "Unable to query Windows serial ports: $($_.Exception.Message)"
    }

    try {
        $entities = @(Get-CimInstance -ClassName Win32_PnPEntity -ErrorAction Stop |
            Where-Object { $_.Name -match '\(COM\d+\)' })
    }
    catch {
        $entities = @()
    }

    foreach ($portName in $portNames) {
        $escapedPort = [regex]::Escape($portName)
        $entity = $entities |
            Where-Object {
                $_.Name -match "\($escapedPort\)" -or
                $_.Caption -match "\($escapedPort\)"
            } |
            Select-Object -First 1

        if ($null -ne $entity) {
            $name = [string]$entity.Name
            $description = [string]$entity.Description
            $pnpDeviceId = [string]$entity.PNPDeviceID
        }
        else {
            $name = $portName
            $description = 'Serial port'
            $pnpDeviceId = ''
        }

        $identity = "$name $description $pnpDeviceId"
        [PSCustomObject]@{
            Port        = $portName.ToUpperInvariant()
            Name        = $name
            Description = $description
            PnpDeviceId = $pnpDeviceId
            LikelyBoard = $identity -match 'CH340|CH341|USB-SERIAL|VID_1A86'
        }
    }
}

function Resolve-HuangshanSerialPort {
    param([string]$Port)

    $ports = @(Get-HuangshanSerialPorts)
    if ($Port) {
        $normalized = $Port.Trim().ToUpperInvariant()
        if ($normalized -notmatch '^COM\d+$') {
            throw "Invalid serial port '$Port'. Expected a value such as COM12."
        }
        if (-not ($ports.Port -contains $normalized)) {
            throw "Serial port $normalized is not currently present. Run scripts\ports.ps1."
        }
        return $normalized
    }

    $likely = @($ports | Where-Object LikelyBoard)
    if ($likely.Count -eq 1) {
        return $likely[0].Port
    }
    if ($likely.Count -gt 1) {
        throw 'Multiple CH340-like devices are connected. Specify -Port COMx explicitly.'
    }
    if ($ports.Count -eq 1) {
        return $ports[0].Port
    }
    if ($ports.Count -eq 0) {
        throw 'No serial port is currently connected.'
    }
    throw 'Multiple serial devices are connected and none is uniquely identifiable. Specify -Port COMx.'
}

