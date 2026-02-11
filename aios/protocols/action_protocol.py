from __future__ import annotations
from typing import Dict, Any, List
import uuid

from aios.protocols.schema import AIOSBaseModel, ActionPlan, Receipt

class VerifiedActionPlan(AIOSBaseModel): # Inherit from base model for timestamp/version
    """
    Represents an ActionPlan after Protocol2 processing, including validation status.
    This is effectively the output of Protocol2.
    """
    action_plan: ActionPlan
    status: str # e.g., "ready_for_execution", "rejected_unsafe", "dry_run_completed"
    validation_messages: List[str] = []
    actuator_preview: str | None = None # What the actuator *would* do in dry-run

def process_action_plan(action_plan: ActionPlan) -> VerifiedActionPlan:
    """
    Processes an ActionPlan received from the Agent, performing validation
    and preparing it for the Actuator.

    Args:
        action_plan: The ActionPlan object from the Agent.

    Returns:
        A VerifiedActionPlan object.
    """
    validation_messages: List[str] = []
    is_safe = True
    actuator_preview = None

    # --- Basic Validation ---
    allowed_action_types = ["TypeString", "Log", "NoAction"]
    if action_plan.action_type not in allowed_action_types:
        is_safe = False
        validation_messages.append(f"Invalid action_type: {action_plan.action_type}")
    
    if action_plan.action_type == "TypeString" and "text" not in action_plan.parameters:
        is_safe = False
        validation_messages.append("TypeString action missing required 'text' parameter.")
    
    if action_plan.action_type == "Log" and "message" not in action_plan.parameters:
        is_safe = False
        validation_messages.append("Log action missing required 'message' parameter.")

    # --- Constraint Enforcement & Safety Validation (Mock for Iteration 5) ---
    # The agent explicitly sets a safety_check flag.
    if not action_plan.constraints.get("safety_check", True):
        is_safe = False
        validation_messages.append("Action plan explicitly marked as unsafe by agent constraints.")
    
    # Example: Blacklist a dangerous action type if not explicitly allowed
    if action_plan.action_type == "DeleteFiles" and "allow_delete" not in action_plan.constraints: # Example
        is_safe = False
        validation_messages.append("Action type 'DeleteFiles' is currently blacklisted for safety reasons.")

    # --- Determine Status ---
    if not is_safe:
        status = "rejected_unsafe"
        actuator_preview = "Action rejected due to safety violations."
    elif action_plan.dry_run:
        status = "dry_run_completed"
        # Simulate what the actuator would do without actually doing it
        if action_plan.action_type == "TypeString":
            actuator_preview = f"Would type: '{action_plan.parameters.get('text', 'N/A')}'"
        elif action_plan.action_type == "Log":
            actuator_preview = f"Would log message: '{action_plan.parameters.get('message', 'N/A')}'"
        elif action_plan.action_type == "NoAction":
            actuator_preview = "Would take no action."
        else:
            actuator_preview = f"Would attempt to execute action type '{action_plan.action_type}'."
    else:
        status = "ready_for_execution"
        actuator_preview = None # No preview needed for actual execution

    return VerifiedActionPlan(
        action_plan=action_plan,
        status=status,
        validation_messages=validation_messages,
        actuator_preview=actuator_preview
    )
