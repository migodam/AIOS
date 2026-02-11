Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, UIAutomationProvider

# Get the temporary directory
$tempDir = $env:TEMP_DIR
if (-not $tempDir) {
    $tempDir = [System.IO.Path]::GetTempPath()
}

# Create a unique filename for the UIA tree output
$timestamp = (Get-Date -Format "yyyyMMddHHmmssfff")
$fileName = "uia_tree_$timestamp.json"
$outputPath = Join-Path $tempDir $fileName

# Define a function to recursively get UIA element properties
function Get-UIAElementProperties {
    param(
        [System.Windows.Automation.AutomationElement]$element,
        [int]$depth = 0,
        [int]$maxDepth = 5 # Limit recursion depth to avoid excessively large trees
    )

    if ($depth -ge $maxDepth -or -not $element) {
        return $null
    }

    $properties = @{
        "Name" = $element.Current.Name
        "AutomationId" = $element.Current.AutomationId
        "ControlType" = $element.Current.ControlType.ProgrammaticName
        "ClassName" = $element.Current.ClassName
        "Rectangle" = $element.Current.BoundingRectangle.ToString()
        "IsKeyboardFocusable" = $element.Current.IsKeyboardFocusable
        "IsEnabled" = $element.Current.IsEnabled
        "ProcessId" = $element.Current.ProcessId
        "NativeWindowHandle" = $element.Current.NativeWindowHandle
    }

    $children = @()
    try {
        $foundChildren = $element.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($child in $foundChildren) {
            $children += Get-UIAElementProperties -element $child -depth ($depth + 1) -maxDepth $maxDepth
        }
    }
    catch {
        # Catch potential errors when accessing children of some elements
        Write-Warning "Could not get children for element $($element.Current.Name): $($($_.Exception.Message))"
    }

    if ($children.Count -gt 0) {
        $properties.Add("Children", $children)
    }

    return $properties
}

# Get the foreground window using Win32 API
Add-Type -MemberDefinition @'
[DllImport("user32.dll")]
public static extern IntPtr GetForegroundWindow();

[DllImport("user32.dll", SetLastError = true)]
public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
'@ -Namespace Win32 -Name NativeMethods

$foregroundWindowHandle = [Win32.NativeMethods]::GetForegroundWindow()

$uiaTree = $null
if ($foregroundWindowHandle -ne [System.IntPtr]::Zero) {
    try {
        $foregroundElement = [System.Windows.Automation.AutomationElement]::FromHandle($foregroundWindowHandle)
        if ($foregroundElement) {
            Write-Host "Capturing UIA tree for foreground window: $($foregroundElement.Current.Name)"
            $uiaTree = Get-UIAElementProperties -element $foregroundElement -maxDepth 3 # Limit depth for foreground window
        } else {
            Write-Warning "Could not get AutomationElement for foreground window handle."
        }
    }
    catch {
        Write-Warning "Error getting AutomationElement from foreground window handle: $($($_.Exception.Message))"
    }
}

# Fallback to Desktop if foreground window UIA fails or isn't found
if (-not $uiaTree) {
    Write-Host "Capturing UIA tree for the Desktop (root element)."
    $uiaTree = Get-UIAElementProperties -element [System.Windows.Automation.AutomationElement]::RootElement -maxDepth 2 # Even shallower depth for root
}

# Convert to JSON and save to file
$windowName = ""
if ($uiaTree) {
    if ($foregroundWindowHandle -ne [System.IntPtr]::Zero -and $foregroundElement) {
        $windowName = $foregroundElement.Current.Name
    } else {
        $windowName = "Desktop"
    }
    $uiaTree | ConvertTo-Json -Depth 100 | Set-Content -Path $outputPath -Encoding UTF8

    # Calculate hash of the saved artifact
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $utilsPath = Join-Path $scriptDir "..\utils"
    $getHashScript = Join-Path $utilsPath "get_file_hash.ps1"
    $artifactHash = (Invoke-Expression "& '$getHashScript' -FilePath '$outputPath'")

    # Construct RawSignal JSON object
    $rawSignal = @{
        timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
        type = "uia_tree"
        artifact_ref = $outputPath
        artifact_hash = $artifactHash
        metadata = @{
            windowName = $windowName
        }
    } | ConvertTo-Json -Depth 10

    Write-Output $rawSignal
} else {
    Write-Error "Failed to capture any UIA tree: $($($_.Exception.Message))"
}
