# main_actuator.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$VerifiedActionPlanJson
)

# Parse the incoming VerifiedActionPlan
$verifiedActionPlan = $VerifiedActionPlanJson | ConvertFrom-Json # Removed -AsHashtable

Write-Host "Actuator received VerifiedActionPlan (Trace ID: $($verifiedActionPlan.trace_id), Type: $($verifiedActionPlan.action_type))"

$receipt = @{
    status = "failed"
    message = "Action could not be executed."
    latency_ms = 0
    post_action_state_ref = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffZ") # Placeholder
    trace_id = $verifiedActionPlan.trace_id
    origin_observation_id = $verifiedActionPlan.origin_observation_id
}

if ($verifiedActionPlan.is_safe -eq $false) {
    $receipt.status = "rejected_unsafe"
    $receipt.message = "Action was marked unsafe by Protocol2 and not executed."
    Write-Warning $receipt.message
    $receipt | ConvertTo-Json -Depth 100
    exit
}

if ($verifiedActionPlan.is_dry_run -eq $true) {
    $receipt.status = "dry_run_success"
    $receipt.message = "Action was in dry-run mode and not actually executed. Preview: $($verifiedActionPlan.actuator_preview)"
    Write-Host $receipt.message
    $receipt | ConvertTo-Json -Depth 100
    exit
}

$startTime = (Get-Date)

try {
    switch ($verifiedActionPlan.action_type) {
        "TypeString" {
            $textToType = $verifiedActionPlan.parameters.text
            if (-not [string]::IsNullOrEmpty($textToType)) {
                # Using WScript.Shell to send keys to the active window
                $wshell = New-Object -ComObject WScript.Shell
                $wshell.SendKeys($textToType)
                $receipt.status = "success"
                $receipt.message = "Successfully typed string: '$textToType'"
                Write-Host $receipt.message
            } else {
                $receipt.status = "failed"
                $receipt.message = "TypeString action failed: 'text' parameter is empty."
                Write-Error $receipt.message
            }
        }
        "Log" {
            $logMessage = $verifiedActionPlan.parameters.message
            if (-not [string]::IsNullOrEmpty($logMessage)) {
                Write-Host "Actuator Log: $logMessage"
                $receipt.status = "success"
                $receipt.message = "Successfully logged message: '$logMessage'"
            } else {
                $receipt.status = "failed"
                $receipt.message = "Log action failed: 'message' parameter is empty."
                Write-Error $receipt.message
            }
        }
        default {
            $receipt.status = "failed"
            $receipt.message = "Unknown action type: '$($verifiedActionPlan.action_type)'."
            Write-Error $receipt.message
        }
    }
} catch {
    $receipt.status = "failed"
    $receipt.message = "Execution error for action type '$($verifiedActionPlan.action_type)': $($($_.Exception.Message))"
    Write-Error $receipt.message
}

$endTime = (Get-Date)
$receipt.latency_ms = ($endTime - $startTime).TotalMilliseconds

$receipt | ConvertTo-Json -Depth 100
