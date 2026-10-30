param(
    [Parameter(Mandatory)][string]$Out,
    [Parameter(Mandatory)][string]$Stop,
    [Parameter(Mandatory)][string]$Log,
    [string]$Devices = "4"
)
# Runs elevated. Captures only the given USBPcap1 device address until $Stop exists.
try {
    Remove-Item $Stop -ErrorAction SilentlyContinue
    # one string with the output path quoted: it contains spaces
    $argLine = '-d \\.\USBPcap1 -o "{0}" --devices {1} --inject-descriptors' -f $Out, $Devices
    $p = Start-Process -FilePath "C:\Program Files\USBPcap\USBPcapCMD.exe" `
        -ArgumentList $argLine -PassThru -WindowStyle Hidden
    "started pid $($p.Id)" | Out-File $Log -Encoding ascii
    while (-not (Test-Path $Stop) -and -not $p.HasExited) { Start-Sleep -Milliseconds 300 }
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
    "stopped exit=$($p.ExitCode)" | Out-File $Log -Append -Encoding ascii
} catch {
    "ERROR: $_" | Out-File $Log -Append -Encoding ascii
}
