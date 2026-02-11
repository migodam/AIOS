Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

# Get the temporary directory from the environment or use a default
$tempDir = $env:TEMP_DIR
if (-not $tempDir) {
    # Fallback to a default temp directory if not provided (shouldn't happen in Gemini CLI)
    $tempDir = [System.IO.Path]::GetTempPath()
}

# Create a unique filename using a timestamp
$timestamp = (Get-Date -Format "yyyyMMddHHmmssfff")
$fileName = "screenshot_$timestamp.jpg"
$outputPath = Join-Path $tempDir $fileName

# Get the screen resolution of the primary screen
$screenResolution = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds

# Create a bitmap with the same resolution as the screen
$bitmap = New-Object System.Drawing.Bitmap $screenResolution.Width, $screenResolution.Height

# Create a graphics object from the bitmap
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)

# Copy the screen to the bitmap
$graphics.CopyFromScreen($screenResolution.Location, [System.Drawing.Point]::Empty, $screenResolution.Size)

# Save the screen capture to the specified file path and format
$bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Jpeg)

# Clean up the graphics and bitmap objects
$graphics.Dispose()
$bitmap.Dispose()

# Calculate hash of the saved artifact
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$utilsPath = Join-Path $scriptDir "..\utils"
$getHashScript = Join-Path $utilsPath "get_file_hash.ps1"
$artifactHash = (Invoke-Expression "& '$getHashScript' -FilePath '$outputPath'")

# Construct RawSignal JSON object
$rawSignal = @{
    timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
    type = "screenshot"
    artifact_ref = $outputPath
    artifact_hash = $artifactHash
    metadata = @{
        width = $screenResolution.Width
        height = $screenResolution.Height
    }
} | ConvertTo-Json -Depth 10

Write-Output $rawSignal
