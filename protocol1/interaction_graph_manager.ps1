# interaction_graph_manager.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$GraphFilePath,
    [Parameter(Mandatory=$false)]
    [string]$NewObservationEvent # Changed from [hashtable] to [string]
)

# Initialize graph structure
function New-InteractionGraph {
    return @{
        nodes = @{}
        edges = @{}
        lastNodeId = 0
        lastEdgeId = 0
    }
}

# Load graph from file or create new if not found
function Load-InteractionGraph {
    param(
        [string]$Path
    )
    if (Test-Path -Path $Path -PathType Leaf) {
        try {
            return (Get-Content -Path $Path -Raw | ConvertFrom-Json) # Removed -AsHashtable
        } catch {
            Write-Warning "Failed to load interaction graph from $Path: $($($_.Exception.Message)). Creating new graph."
            return New-InteractionGraph
        }
    } else {
        return New-InteractionGraph
    }
}

# Save graph to file
function Save-InteractionGraph {
    param(
        [hashtable]$Graph,
        [string]$Path
    )
    $Graph | ConvertTo-Json -Depth 100 | Set-Content -Path $Path -Encoding UTF8
}

# Function to add or update a node
function Add-OrUpdate-Node {
    param(
        [hashtable]$Graph,
        [string]$Type, # e.g., "app_state", "ui_context", "environment_state"
        [hashtable]$Properties # Node-specific data
    )

    # Simple heuristic for node uniqueness: check existing nodes by type and a hash of properties
    # In a real system, this would be more sophisticated (e.g., semantic hashing, direct comparison)
    $nodeHash = ($Properties | ConvertTo-Json -Compress) | Get-FileHash -Algorithm SHA256 | Select-Object -ExpandProperty Hash
    
    foreach ($nodeId in $Graph.nodes.Keys) {
        # Ensure properties are compared correctly when they are PSCustomObject
        $existingPropertiesJson = ($Graph.nodes[$nodeId].properties | ConvertTo-Json -Compress)
        $newPropertiesJson = ($Properties | ConvertTo-Json -Compress)

        if ($Graph.nodes[$nodeId].type -eq $Type -and ($Graph.nodes[$nodeId].hash -eq $nodeHash -or $existingPropertiesJson -eq $newPropertiesJson)) {
            Write-Verbose "Existing node found for type $($Type) with hash $($nodeHash): $($nodeId)"
            return $nodeId
        }
    }

    # If no existing node, create a new one
    $Graph.lastNodeId++
    $newNodeId = "node_" + $Graph.lastNodeId
    $Graph.nodes[$newNodeId] = @{
        id = $newNodeId
        type = $Type
        properties = $Properties
        hash = $nodeHash # Store hash for future comparisons
        created = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
    }
    Write-Verbose "Created new node $($newNodeId) (type: $($Type))"
    return $newNodeId
}

# Function to add an edge
function Add-Edge {
    param(
        [hashtable]$Graph,
        [string]$SourceNodeId,
        [string]$TargetNodeId,
        [string]$Type, # e.g., "user_action", "agent_action", "state_transition"
        [hashtable]$Properties # Edge-specific data
    )

    $Graph.lastEdgeId++
    $newEdgeId = "edge_" + $Graph.lastEdgeId
    $Graph.edges[$newEdgeId] = @{
        id = $newEdgeId
        source = $SourceNodeId
        target = $TargetNodeId
        type = $Type
        properties = $Properties
        created = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ")
    }
    Write-Verbose "Created new edge $($newEdgeId) (type: $($Type)) from $($SourceNodeId) to $($TargetNodeId)"
    return $newEdgeId
}

# Main logic for updating the graph with a new observation event
function Update-InteractionGraph {
    param(
        [hashtable]$Graph,
        [PSCustomObject]$ObservationEvent # Expecting PSCustomObject after ConvertFrom-Json
    )

    if (-not $ObservationEvent) {
        Write-Warning "No ObservationEvent provided for graph update."
        return $Graph
    }

    # Convert PSCustomObject properties to hashtables for Add-OrUpdate-Node
    $uiState = $ObservationEvent.ui_state | ConvertTo-Json | ConvertFrom-Json -AsHashtable
    $environmentState = $ObservationEvent.environment_state | ConvertTo-Json | ConvertFrom-Json -AsHashtable
    $operationContext = $ObservationEvent.operation_context | ConvertTo-Json | ConvertFrom-Json -AsHashtable

    # Extract relevant info from ObservationEvent to create/update nodes and edges
    $timestamp = $ObservationEvent.timestamp
    $observationId = $ObservationEvent.observation_id
    
    # Create/update UI State Node
    $uiNodeId = Add-OrUpdate-Node -Graph $Graph -Type "ui_context" -Properties $uiState

    # Create/update Environment State Node
    $envNodeId = Add-OrUpdate-Node -Graph $Graph -Type "environment_state" -Properties $environmentState

    # Create/update Operation Context Node (represents the agent's interpretation)
    $opContextNodeId = Add-OrUpdate-Node -Graph $Graph -Type "operation_context" -Properties $operationContext

    $observationNodeId = Add-OrUpdate-Node -Graph $Graph -Type "observation_frame" -Properties @{
        timestamp = $timestamp
        observation_id = $observationId
        summary = "Aggregated observation frame."
    }

    Add-Edge -Graph $Graph -SourceNodeId $observationNodeId -TargetNodeId $uiNodeId -Type "contains_ui_state" -Properties @{}
    Add-Edge -Graph $Graph -SourceNodeId $observationNodeId -TargetNodeId $envNodeId -Type "contains_environment_state" -Properties @{}
    Add-Edge -Graph $Graph -SourceNodeId $observationNodeId -TargetNodeId $opContextNodeId -Type "contains_operation_context" -Properties @{}

    return $Graph
}


# Main execution logic for the script
$graph = Load-InteractionGraph -Path $GraphFilePath

if ($NewObservationEvent) {
    Write-Host "Updating interaction graph with new observation event..."
    # Convert NewObservationEvent from JSON string to PSCustomObject, then pass
    $parsedObservationEvent = $NewObservationEvent | ConvertFrom-Json
    $graph = Update-InteractionGraph -Graph $graph -ObservationEvent $parsedObservationEvent
    Save-InteractionGraph -Graph $graph -Path $GraphFilePath
    Write-Host "Interaction graph updated and saved to $GraphFilePath."
} else {
    Write-Host "No new observation event provided. Loaded graph from $GraphFilePath."
}

# Output the current state of the graph (or a simplified view)
# For now, just output the entire graph for debugging/initial verification
$graph | ConvertTo-Json -Depth 100
