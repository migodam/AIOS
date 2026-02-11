# main_agent.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$ObservationEventJson,
    [Parameter(Mandatory=$true)]
    [string]$UpdatedGraphPath
)

# Parse the incoming ObservationEvent
$observationEvent = $ObservationEventJson | ConvertFrom-Json # Removed -AsHashtable

# Define paths to Protocol1 scripts (for Orient step - querying graph)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$protocol1Path = Join-Path $scriptDir "..\protocol1"
$graphManagerScript = Join-Path $protocol1Path "interaction_graph_manager.ps1"

# --- OODA Loop ---

# 1. Observe (already done - input is ObservationEvent)
Write-Host "Agent Observing: Received ObservationEvent (ID: $($observationEvent.observation_id))"

# 2. Orient (Query Interaction Graph)
Write-Host "Agent Orienting: Querying Interaction Graph from $UpdatedGraphPath..."
$currentGraph = $null
try {
    # The graph manager outputs the graph when called without a NewObservationEvent
    $graphOutput = Invoke-Expression "& '$graphManagerScript' -GraphFilePath '$UpdatedGraphPath'"
    $currentGraph = $graphOutput | ConvertFrom-Json # Removed -AsHashtable
    # If the ConvertFrom-Json result is a PSCustomObject, convert it to a Hashtable for consistent access
    if ($currentGraph -is [PSCustomObject]) {
        $currentGraph = $currentGraph | ConvertTo-Json | ConvertFrom-Json -AsHashtable
    }
    Write-Host "Graph loaded. Nodes: $($currentGraph.nodes.Count), Edges: $($currentGraph.edges.Count)."
} catch {
    Write-Warning "Failed to load current interaction graph: $($($_.Exception.Message))"
}

# Example Orient logic: Check for specific UI elements or context
$focusedWindowName = $observationEvent.ui_state.focused_window_name
$hasNotepad = ($focusedWindowName -like "*Notepad*")
$hasLogs = ($observationEvent.environment_state.recent_logs -ne "")

# 3. Decide (Generate ActionPlan - rule-based for now)
Write-Host "Agent Deciding: Applying rules..."
$actionType = "NoAction"
$actionParameters = @{}
$decisionSummary = "No specific action decided based on current observation."

if ($hasNotepad) {
    $actionType = "TypeString"
    $actionParameters = @{
        "text" = "Hello AIOS World from Agent! $($observationEvent.timestamp)"
    }
    $decisionSummary = "Notepad detected. Decided to type a message."
} elseif ($hasLogs) {
    $actionType = "Log"
    $actionParameters = @{
        "message" = "Logs were observed. Agent acknowledges."
    }
    $decisionSummary = "Logs observed. Decided to acknowledge."
}

# 4. Act (Output Protocol2 Action Instruction)
Write-Host "Agent Acting: Emitting ActionPlan..."

$actionPlan = @{
    action_type = $actionType
    parameters = $actionParameters
    constraints = @{
        "safety_check" = "true" # Placeholder for future safety checks
    }
    trace_id = [System.Guid]::NewGuid().ToString()
    dry_run = $false # Will be configurable
    # Add a reference to the observation that led to this action
    origin_observation_id = $observationEvent.observation_id
}

$output = @{
    ActionPlan = $actionPlan
    DecisionSummary = $decisionSummary
}

$output | ConvertTo-Json -Depth 100
