from __future__ import annotations
import time
from typing import Any, Dict
from datetime import datetime

# Import pynput for keyboard control
from pynput.keyboard import Controller as KeyboardController

from aios.protocols.schema import Receipt, EventType, Event, ActionPlan
from aios.protocols.action_protocol import VerifiedActionPlan

def execute_action(verified_action_plan: VerifiedActionPlan) -> Receipt:
    """
    Executes the action specified in the VerifiedActionPlan.

    Args:
        verified_action_plan: A VerifiedActionPlan object from Protocol2.

    Returns:
        A Receipt object detailing the outcome of the execution.
    """
    start_time = time.perf_counter()
    action = verified_action_plan.action_plan
    
    receipt_status = "failure"
    receipt_message = "Action could not be executed due to unknown error."

    try:
        if verified_action_plan.status == "rejected_unsafe":
            receipt_status = "rejected_unsafe"
            receipt_message = "Action was rejected by Protocol2 as unsafe."
            print(f"Actuator: {receipt_message}")
            return Receipt(
                action_id=action.action_id,
                status=receipt_status,
                message=receipt_message,
                latency_ms=(time.perf_counter() - start_time) * 1000
            )
        
        if verified_action_plan.status == "dry_run_completed":
            receipt_status = "dry_run_success"
            receipt_message = f"Action completed successfully in dry-run mode. Preview: {verified_action_plan.actuator_preview}"
            print(f"Actuator: {receipt_message}")
            return Receipt(
                action_id=action.action_id,
                status=receipt_status,
                message=receipt_message,
                latency_ms=(time.perf_counter() - start_time) * 1000
            )

        if verified_action_plan.status == "ready_for_execution":
            print(f"Actuator: Executing action '{action.action_type}' (ID: {action.action_id})...")
            keyboard = KeyboardController()
            
            if action.action_type == "TypeString":
                text_to_type = action.parameters.get("text")
                if text_to_type:
                    keyboard.type(str(text_to_type))
                    receipt_status = "success"
                    receipt_message = f"Successfully typed: '{text_to_type}'"
                else:
                    receipt_status = "failure"
                    receipt_message = "TypeString action missing 'text' parameter."
            
            elif action.action_type == "Log":
                message_to_log = action.parameters.get("message")
                if message_to_log:
                    print(f"Actuator Log (Actual Execution): {message_to_log}")
                    receipt_status = "success"
                    receipt_message = f"Successfully logged message: '{message_to_log}'"
                else:
                    receipt_status = "failure"
                    receipt_message = "Log action missing 'message' parameter."
            
            elif action.action_type == "NoAction":
                receipt_status = "success"
                receipt_message = "No action was required or taken."

            else:
                receipt_status = "failure"
                receipt_message = f"Unknown action type for execution: '{action.action_type}'"

        else:
            receipt_status = "failure"
            receipt_message = f"Invalid VerifiedActionPlan status for execution: '{verified_action_plan.status}'"

    except Exception as e:
        receipt_status = "failure"
        receipt_message = f"Execution of action '{action.action_type}' failed: {e}"
        print(f"Actuator ERROR: {receipt_message}")
        
    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000

    return Receipt(
        action_id=action.action_id,
        status=receipt_status,
        message=receipt_message,
        latency_ms=latency_ms,
        origin_observation_id=action.origin_observation_id # Link back to original observation
    )
