# protocol1_aggregator.ps1

# Define paths to observer scripts relative to this script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$observersPath = Join-Path $scriptDir "..\observers"
$screenshotScript = Join-Path $observersPath "capture_screenshot.ps1"
$uiaScript = Join-Path $observersPath "get_uia_tree.ps1"
$logTailScript = Join-Path $observersPath "tail_log_file.ps1"

# Define a temporary log file path for the log observer
# This will be created within the main temp directory
$tempDir = $env:TEMP_DIR
if (-not $tempDir) {
    $tempDir = [System.IO.Path]::GetTempPath()
}
$controlledLogFile = Join-Path $tempDir "aios_controlled_log.txt"

# Array to hold all raw signals
$allRawSignals = @()

# --- Invoke Screenshot Observer ---
Write-Host "Invoking Screenshot Observer..."
try {
    $screenshotRawSignalJson = (Invoke-Expression "& '$screenshotScript'")
    $allRawSignals += (ConvertFrom-Json $screenshotRawSignalJson)
} catch {
    Write-Warning "Screenshot Observer failed: $($_.Exception.Message)"
}

# --- Invoke UIA Observer ---
Write-Host "Invoking UIA Observer..."
try {
    $uiaRawSignalJson = (Invoke-Expression "& '$uiaScript'")
    $allRawSignals += (ConvertFrom-Json $uiaRawSignalJson)
} catch {
    Write-Warning "UIA Observer failed: $($_.Exception.Message)"
}

# --- Invoke Log Tail Observer ---
Write-Host "Invoking Log Tail Observer..."
# For testing purposes, let's write some content to the controlled log file
"Log entry 1: $(Get-Date)" | Out-File -FilePath $controlledLogFile -Append -Encoding UTF8
"Log entry 2: $(Get-Date)" | Out-File -FilePath $controlledLogFile -Append -Encoding UTF8

try {
    $logRawSignalJson = (Invoke-Expression "& '$logTailScript' -LogFilePath '$controlledLogFile'")
    $allRawSignals += (ConvertFrom-Json $logRawSignalJson)
} catch {
    Write-Warning "Log Tail Observer failed: $($_.Exception.Message)"
}

# Output the aggregated raw signals as a JSON array
$allRawSignals | ConvertTo-Json -Depth 100
