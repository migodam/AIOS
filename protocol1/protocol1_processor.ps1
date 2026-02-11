# Define paths to observer scripts relative to this script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$observersPath = Join-Path $scriptDir "..\observers"
$screenshotScript = Join-Path $observersPath "capture_screenshot.ps1"
$uiaScript = Join-Path $observersPath "get_uia_tree.ps1"
$logTailScript = Join-Path $observersPath "tail_log_file.ps1"

# Define path to interaction graph manager script
$graphManagerScript = Join-Path $scriptDir "interaction_graph_manager.ps1"

# Define a temporary log file path for the log observer and a path for the persistent graph
$tempDir = $env:TEMP_DIR
if (-not $tempDir) {
    $tempDir = [System.IO.Path]::GetTempPath()
}
$controlledLogFile = Join-Path $tempDir "aios_controlled_log.txt"
$persistentGraphFile = Join-Path $tempDir "interaction_graph.json"

# --- Raw Signal Collection ---
function Get-RawSignals {
    $allRawSignals = @()

    # --- Invoke Screenshot Observer ---
    Write-Host "Invoking Screenshot Observer..."
    try {
        $screenshotRawSignalJson = (Invoke-Expression "& '$screenshotScript'")
        $allRawSignals += (ConvertFrom-Json $screenshotRawSignalJson)
    } catch {
        Write-Warning "Screenshot Observer failed: $($($_.Exception.Message))"
    }

    # --- Invoke UIA Observer ---
    Write-Host "Invoking UIA Observer..."
    try {
        $uiaRawSignalJson = (Invoke-Expression "& '$uiaScript'")
        $allRawSignals += (ConvertFrom-Json $uiaRawSignalJson)
    } catch {
        Write-Warning "UIA Observer failed: $($($_.Exception.Message))"
    }

    # --- Invoke Log Tail Observer ---
    Write-Host "Invoking Log Tail Observer..."
    "Log entry 1: $(Get-Date)" | Out-File -FilePath $controlledLogFile -Append -Encoding UTF8
    "Log entry 2: $(Get-Date)" | Out-File -FilePath $controlledLogFile -Append -Encoding UTF8

    try {
        $logRawSignalJson = (Invoke-Expression "& '$logTailScript' -LogFilePath '$controlledLogFile'")
        $allRawSignals += (ConvertFrom-Json $logRawSignalJson)
    } catch {
        Write-Warning "Log Tail Observer failed: $($($_.Exception.Message))"
    }

    return $allRawSignals
}

# --- ObservationEvent Schema (simplified for validation) ---
$observationEventSchema = @{
    Required = @("timestamp", "observation_id", "raw_signals", "ui_state", "environment_state", "operation_context")
    Properties = @{
        "timestamp" = @{ Type = "string" }
        "observation_id" = @{ Type = "string" }
        "raw_signals" = @{ Type = "array" }
        "ui_state" = @{ Type = "object"; Required = @("focused_window_name", "uia_elements", "screenshot_description") }
        "environment_state" = @{ Type = "object"; Required = @("recent_logs") }
        "operation_context" = @{ Type = "object"; Required = @("potential_intent", "summary") }
    }
}

# --- Schema Validation Function ---
function Test-ObservationEventSchema {
    param(
        [hashtable]$observationEvent,
        [hashtable]$schema
    )

    foreach ($prop in $schema.Required) {
        if (-not $observationEvent.ContainsKey($prop)) {
            Write-Warning "Schema validation failed: Missing required property '$prop'."
            return $false
        }
    }

# Define paths to observer scripts relative to this script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$observersPath = Join-Path $scriptDir "..\observers"
$screenshotScript = Join-Path $observersPath "capture_screenshot.ps1"
$uiaScript = Join-Path $observersPath "get_uia_tree.ps1"
$logTailScript = Join-Path $observersPath "tail_log_file.ps1"

# Define path to interaction graph manager script
$graphManagerScript = Join-Path $scriptDir "interaction_graph_manager.ps1"

# Define a temporary log file path for the log observer and a path for the persistent graph
$tempDir = $env:TEMP_DIR
if (-not $tempDir) {
    $tempDir = [System.IO.Path]::GetTempPath()
}
$controlledLogFile = Join-Path $tempDir "aios_controlled_log.txt"
$persistentGraphFile = Join-Path $tempDir "interaction_graph.json"

# --- Raw Signal Collection ---
function Get-RawSignals {
    $allRawSignals = @()

    # --- Invoke Screenshot Observer ---
    Write-Host "Invoking Screenshot Observer..."
    try {
        $screenshotRawSignalJson = (Invoke-Expression "& '$screenshotScript'")
        $allRawSignals += (ConvertFrom-Json $screenshotRawSignalJson)
    } catch {
        Write-Warning "Screenshot Observer failed: $($($_.Exception.Message))"
    }

    # --- Invoke UIA Observer ---
    Write-Host "Invoking UIA Observer..."
    try {
        $uiaRawSignalJson = (Invoke-Expression "& '$uiaScript'")
        $allRawSignals += (ConvertFrom-Json $uiaRawSignalJson)
    } catch {
        Write-Warning "UIA Observer failed: $($($_.Exception.Message))"
    }

    # --- Invoke Log Tail Observer ---
    Write-Host "Invoking Log Tail Observer..."
    "Log entry 1: $(Get-Date)" | Out-File -FilePath $controlledLogFile -Append -Encoding UTF8
    "Log entry 2: $(Get-Date)" | Out-File -FilePath $controlledLogFile -Append -Encoding UTF8

    try {
        $logRawSignalJson = (Invoke-Expression "& '$logTailScript' -LogFilePath '$controlledLogFile'")
        $allRawSignals += (ConvertFrom-Json $logRawSignalJson)
    } catch {
        Write-Warning "Log Tail Observer failed: $($($_.Exception.Message))"
    }

    return $allRawSignals
}

# --- ObservationEvent Schema (simplified for validation) ---
$observationEventSchema = @{
    Required = @("timestamp", "observation_id", "raw_signals", "ui_state", "environment_state", "operation_context")
    Properties = @{
        "timestamp" = @{ Type = "string" }
        "observation_id" = @{ Type = "string" }
        "raw_signals" = @{ Type = "array" }
        "ui_state" = @{ Type = "object"; Required = @("focused_window_name", "uia_elements", "screenshot_description") }
        "environment_state" = @{ Type = "object"; Required = @("recent_logs") }
        "operation_context" = @{ Type = "object"; Required = @("potential_intent", "summary") }
    }
}

# --- Schema Validation Function ---
function Test-ObservationEventSchema {
    param(
        [PSCustomObject]$observationEvent, # Expect PSCustomObject
        [hashtable]$schema
    )

    foreach ($prop in $schema.Required) {
        if (-not $observationEvent.$prop) { # Access property directly
            Write-Warning "Schema validation failed: Missing required property '$prop'."
            return $false
        }
    }

    if ($observationEvent.timestamp.GetType().Name -ne "String") { Write-Warning "Timestamp not string."; return $false }
    if ($observationEvent.observation_id.GetType().Name -ne "String") { Write-Warning "observation_id not string."; return $false }
    # Check if raw_signals is an array and not null
    if (-not $observationEvent.raw_signals -or $observationEvent.raw_signals.GetType().Name -ne "Object[]") { Write-Warning "raw_signals not array or is null."; return $false }

    # Further checks for nested objects (simplified)
    if ($observationEvent.ui_state) {
        foreach ($prop in $schema.Properties.ui_state.Required) {
            if (-not $observationEvent.ui_state.$prop) {
                Write-Warning "Schema validation failed: Missing required UI state property '$prop'."
                return $false
            }
        }
    } else { Write-Warning "Missing ui_state."; return $false }
    
    if ($observationEvent.environment_state) {
        foreach ($prop in $schema.Properties.environment_state.Required) {
            if (-not $observationEvent.environment_state.$prop) {
                Write-Warning "Schema validation failed: Missing required environment state property '$prop'."
                return $false
            }
        }
    } else { Write-Warning "Missing environment_state."; return $false }

    if ($observationEvent.operation_context) {
        foreach ($prop in $schema.Properties.operation_context.Required) {
            if (-not $observationEvent.operation_context.$prop) {
                Write-Warning "Schema validation failed: Missing required operation context property '$prop'."
                return $false
            }
        }
    } else { Write-Warning "Missing operation_context."; return $false }

    return $true
}

# --- Invoke-RuleBasedParse Function (formerly Invoke-SimulatedLLMParse) ---
function Invoke-RuleBasedParse {
    param(
        [array]$rawSignals
    )

    $uiState = $null
    $environmentState = $null
    $focusedWindowName = "Unknown Window"
    $recentLogs = ""
    $uiaElements = @()
    $screenshotDescription = "A typical desktop screenshot."
    $potentialIntent = "Monitor system activity."
    $summary = "The system is currently observed, but specific user interaction is unclear."

    foreach ($signal in $rawSignals) {
        if ($signal.type -eq "uia_tree") {
            try {
                $uiaContent = Get-Content -Path $signal.artifact_ref -Raw | ConvertFrom-Json
                $focusedWindowName = $signal.metadata.windowName
                $uiaElements = @($uiaContent.Children | Select-Object Name, ControlType | ForEach-Object { "$($_.ControlType): $($_.Name)" })
                if ($uiaElements.Count -gt 5) { $uiaElements = $uiaElements[0..4] }
            } catch {
                Write-Warning "Failed to parse UIA artifact: $($($_.Exception.Message))"
            }
        } elseif ($signal.type -eq "log_tail") {
            try {
                $recentLogs = Get-Content -Path $signal.artifact_ref -Raw
                if ($recentLogs.Length -gt 500) { $recentLogs = $recentLogs.Substring(0, 500) + "..." }
            } catch {
                Write-Warning "Failed to read log artifact: $($($_.Exception.Message))"
            }
        }
        if ($signal.type -eq "screenshot") {
             $screenshotDescription = "Full desktop screenshot captured at $((Get-Date).ToString("T"))."
        }
    }
    
    if ($focusedWindowName -ne "Unknown Window" -and $focusedWindowName -ne "Desktop") {
        $potentialIntent = "User is focused on '$focusedWindowName'."
        $summary = "Observation indicates user interaction primarily within '$focusedWindowName'. "
    }
    if ($recentLogs -ne "") {
        $summary += "Recent system logs show: $($recentLogs.Split("`n")[0])..."
        $potentialIntent += " Also, system events are noted in the logs."
    }

    $uiState = @{
        focused_window_name = $focusedWindowName
        uia_elements = $uiaElements
        screenshot_description = $screenshotDescription
    }
    $environmentState = @{
        recent_logs = $recentLogs
    }
    $operationContext = @{
        potential_intent = $potentialIntent
        summary = $summary
    }

    $observationEvent = @{
        timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
        observation_id = [System.Guid]::NewGuid().ToString()
        raw_signals = $rawSignals
        ui_state = $uiState
        environment_state = $environmentState
        operation_context = $operationContext
    }

    return $observationEvent
}

# --- Invoke-ExternalLLMParse Function ---
function Invoke-ExternalLLMParse {
    param(
        [array]$rawSignals,
        [string]$llmEndpoint = "http://localhost:8080/llm_parse", # Configurable LLM endpoint
        [int]$timeoutSec = 10
    )

    Write-Host "Attempting to call external LLM at $llmEndpoint..."
    $externalLLMOutput = $null
    try {
        # Prepare payload
        $payload = @{
            raw_signals = $rawSignals
            timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
        } | ConvertTo-Json -Compress

        # Make HTTP POST request
        $response = Invoke-RestMethod -Uri $llmEndpoint -Method Post -ContentType "application/json" -Body $payload -TimeoutSec $timeoutSec
        $externalLLMOutput = $response | ConvertFrom-Json # Removed -AsHashtable
        Write-Host "External LLM call successful."
        return $externalLLMOutput
    } catch {
        Write-Warning "External LLM call failed: $($($_.Exception.Message)). Falling back to rule-based parsing."
        return $null
    }
}

# --- Fallback Mechanism (remains the same) ---
function Invoke-FallbackParse {
    param(
        [array]$rawSignals
    )

    Write-Warning "Falling back to rule-based parsing due to LLM failure or invalid output."

    $focusedWindowName = "Unknown Window (fallback)"
    $recentLogs = "No LLM interpretation for logs (fallback)."
    $screenshotDescription = "Raw screenshot artifact available (fallback)."
    $uiaElements = @()

    foreach ($signal in $rawSignals) {
        if ($signal.type -eq "uia_tree") {
            try {
                $focusedWindowName = $signal.metadata.windowName + " (fallback)"
                $uiaContent = Get-Content -Path $signal.artifact_ref -Raw | ConvertFrom-Json
                $uiaElements = @($uiaContent.Children | Select-Object Name, ControlType | ForEach-Object { "$($_.ControlType): $($_.Name)" })
                if ($uiaElements.Count -gt 3) { $uiaElements = $uiaElements[0..2] }
            } catch {}
        } elseif ($signal.type -eq "log_tail") {
            try {
                $recentLogs = (Get-Content -Path $signal.artifact_ref -Raw).Substring(0, [System.Math]::Min(500, (Get-Content -Path $signal.artifact_ref -Raw).Length)) + " (fallback, truncated)"
            } catch {}
        }
    }

    $uiState = @{
        focused_window_name = $focusedWindowName
        uia_elements = $uiaElements
        screenshot_description = $screenshotDescription
    }
    $environmentState = @{
        recent_logs = $recentLogs
    }
    $operationContext = @{
        potential_intent = "Low-fidelity intent derived from raw signals (fallback)."
        summary = "Fallback parsing: Basic UI elements and truncated logs observed."
    }

    $observationEvent = @{
        timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
        observation_id = [System.Guid]::NewGuid().ToString()
        raw_signals = $rawSignals
        ui_state = $uiState
        environment_state = $environmentState
        operation_context = $operationContext
    }

    return $observationEvent
}

# --- Main Logic ---
$rawSignals = Get-RawSignals

$llmParsedObservation = $null
$externalLLMAttempt = Invoke-ExternalLLMParse -rawSignals $rawSignals

if ($externalLLMAttempt -and (Test-ObservationEventSchema -observationEvent $externalLLMAttempt -schema $observationEventSchema)) {
    Write-Host "External LLM parsing successful and schema valid."
    $llmParsedObservation = $externalLLMAttempt
} else {
    Write-Warning "External LLM parsing failed or output invalid. Falling back to rule-based parsing."
    $llmParsedObservation = Invoke-RuleBasedParse -rawSignals $rawSignals
}

$finalObservationEvent = $null
if ($llmParsedObservation -and (Test-ObservationEventSchema -observationEvent $llmParsedObservation -schema $observationEventSchema)) {
    Write-Host "Final ObservationEvent is valid."
    $finalObservationEvent = $llmParsedObservation
} else {
    Write-Warning "Rule-based parsing also failed validation. Using simplified fallback."
    $finalObservationEvent = Invoke-FallbackParse -rawSignals $rawSignals
}


# Update interaction graph
try {
    Write-Host "Updating Interaction Graph..."
    $graphUpdateResult = Invoke-Expression "& '$graphManagerScript' -GraphFilePath '$persistentGraphFile' -NewObservationEvent '$($finalObservationEvent | ConvertTo-Json -Compress)'"
    $updatedGraph = $graphUpdateResult | ConvertFrom-Json
    Write-Host "Interaction Graph updated. Graph file: $persistentGraphFile"
} catch {
    Write-Error "Failed to update interaction graph: $($($_.Exception.Message))"
}

# Output the final ObservationEvent and the path to the updated graph
$output = @{
    ObservationEvent = $finalObservationEvent
    UpdatedGraphPath = $persistentGraphFile
}

$output | ConvertTo-Json -Depth 100
