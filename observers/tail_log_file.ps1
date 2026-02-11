param(
    [Parameter(Mandatory=$true)]
    [string]$LogFilePath
)

# Ensure the directory exists
$logFileDirectory = Split-Path -Path $LogFilePath -Parent
if (-not (Test-Path -Path $logFileDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $logFileDirectory -Force | Out-Null
}

# Ensure the log file exists; create it if it doesn't
if (-not (Test-Path -Path $LogFilePath -PathType Leaf)) {
    New-Item -ItemType File -Path $LogFilePath -Force | Out-Null
}

# Read the entire content of the log file
$logContent = Get-Content -Path $LogFilePath -Raw -ErrorAction SilentlyContinue

# Get the temporary directory
$tempDir = $env:TEMP_DIR
if (-not $tempDir) {
    $tempDir = [System.IO.Path]::GetTempPath()
}

# Create a unique filename for the temporary log content artifact
$timestamp = (Get-Date -Format "yyyyMMddHHmmssfff")
$artifactFileName = "log_artifact_$timestamp.txt"
$artifactPath = Join-Path $tempDir $artifactFileName

# Write the log content to a temporary artifact file
Set-Content -Path $artifactPath -Value $logContent -Encoding UTF8

# Calculate hash of the saved artifact
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$utilsPath = Join-Path $scriptDir "..\utils"
$getHashScript = Join-Path $utilsPath "get_file_hash.ps1"
$artifactHash = (Invoke-Expression "& '$getHashScript' -FilePath '$artifactPath'")

# Construct RawSignal JSON object
$rawSignal = @{
    timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
    type = "log_tail"
    artifact_ref = $artifactPath
    artifact_hash = $artifactHash
    metadata = @{
        originalLogFilePath = $LogFilePath
    }
} | ConvertTo-Json -Depth 10

Write-Output $rawSignal
