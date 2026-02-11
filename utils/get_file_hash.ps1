param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

if (-not (Test-Path -Path $FilePath -PathType Leaf)) {
    Write-Error "File not found: $FilePath"
    exit 1
}

# Calculate SHA256 hash
try {
    $hash = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash
    Write-Output $hash
}
catch {
    Write-Error "Failed to calculate hash for $FilePath: $($($_.Exception.Message))"
    exit 1
}
