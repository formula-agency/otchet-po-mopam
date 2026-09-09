param(
    [string]$SshHost = "45.91.238.53",
    [string]$SshUser = "root",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\formula_templab_bastion"
)

$ErrorActionPreference = "Stop"
$ports = 27018, 27019
$existing = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -eq "127.0.0.1" -and $_.LocalPort -in $ports }

if (($existing.LocalPort | Sort-Object -Unique).Count -eq $ports.Count) {
    Write-Output "TempLab tunnel is already running."
    exit 0
}

if (-not (Test-Path -LiteralPath $KeyPath)) {
    throw "SSH key not found: $KeyPath"
}

$sshArguments = @(
    "-N",
    "-i", $KeyPath,
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "IdentitiesOnly=yes",
    "-o", "ServerAliveInterval=30",
    "-L", "127.0.0.1:27018:94.198.221.153:27017",
    "-L", "127.0.0.1:27019:89.223.71.184:27017",
    "$SshUser@$SshHost"
)

$process = Start-Process ssh -ArgumentList $sshArguments -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2

foreach ($port in $ports) {
    $connection = Test-NetConnection 127.0.0.1 -Port $port -WarningAction SilentlyContinue
    if (-not $connection.TcpTestSucceeded) {
        Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        throw "SSH tunnel did not open local port $port."
    }
}

Write-Output "TempLab tunnel opened (PID $($process.Id))."
