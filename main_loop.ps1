# main_loop.ps1 - Orchestrates the AIOS Closed Loop

# Define paths to component scripts
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$protocol1ProcessorScript = Join-Path $scriptDir "protocol1/protocol1_processor.ps1"
$agentScript = Join-Path $scriptDir "agent/main_agent.ps1"
$protocol2ProcessorScript = Join-Path $scriptDir "protocol2/protocol2_processor.ps1"
$actuatorScript = Join-Path $scriptDir "actuator/main_actuator.ps1"

Write-Host "Starting AIOS Closed Loop Orchestration..."

# --- Step 1: Protocol1 (Observe -> Parse -> Learn) ---
Write-Host "Executing Protocol1 Processor..."
$protocol1Output = (Invoke-Expression "& '$protocol1ProcessorScript'")
$protocol1Result = $protocol1Output | ConvertFrom-Json

$observationEvent = $protocol1Result.ObservationEvent
$updatedGraphPath = $protocol1Result.UpdatedGraphPath

if (-not $observationEvent) {
    Write-Error "Protocol1 Processor failed to produce an ObservationEvent. Exiting."
    exit 1
}

Write-Host "Protocol1 completed. ObservationEvent (ID: $($observationEvent.observation_id)) and Graph updated at $updatedGraphPath."

# --- Step 2: Agent (Decide) ---
Write-Host "Executing Agent..."
$agentOutput = (Invoke-Expression "& '$agentScript' -ObservationEventJson '$($observationEvent | ConvertTo-Json -Compress)' -UpdatedGraphPath '$updatedGraphPath'")
$agentResult = $agentOutput | ConvertFrom-Json

$actionPlan = $agentResult.ActionPlan
$decisionSummary = $agentResult.DecisionSummary

if (-not $actionPlan) {
    Write-Error "Agent failed to produce an ActionPlan. Exiting."
    exit 1
}

Write-Host "Agent completed. Decision: '$decisionSummary'. ActionPlan (Type: $($actionPlan.action_type), Trace ID: $($actionPlan.trace_id))."

# --- Step 3: Protocol2 (Action Planning) ---
Write-Host "Executing Protocol2 Processor..."
$protocol2Output = (Invoke-Expression "& '$protocol2ProcessorScript' -ActionPlanJson '$($actionPlan | ConvertTo-Json -Compress)'")
$protocol2Result = $protocol2Output | ConvertFrom-Json

$verifiedActionPlan = $protocol2Result

if (-not $verifiedActionPlan) {
    Write-Error "Protocol2 Processor failed to produce a VerifiedActionPlan. Exiting."
    exit 1
}

Write-Host "Protocol2 completed. VerifiedActionPlan (Status: $($verifiedActionPlan.status))."

# --- Step 4: Actuator (Act) ---
Write-Host "Executing Actuator..."
$actuatorOutput = (Invoke-Expression "& '$actuatorScript' -VerifiedActionPlanJson '$($verifiedActionPlan | ConvertTo-Json -Compress)'")
$receipt = $actuatorOutput | ConvertFrom-Json

if (-not $receipt) {
    Write-Error "Actuator failed to produce a Receipt. Exiting."
    exit 1
}

Write-Host "Actuator completed. Receipt (Status: $($receipt.status), Message: $($receipt.message))."

Write-Host "AIOS Closed Loop Iteration Complete."

# Output the final receipt
$receipt | ConvertTo-Json -Depth 100
