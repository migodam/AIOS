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
    is_safe = True # Temporarily assuming safe as per user request
    actuator_preview = None

    # --- Basic Validation (Temporarily Disabled for Debugging) ---
    # Allowed action types are now part of the schema's Literal type, but keeping this for future reference
    allowed_action_types_for_ref = ["TypeString", "KeyPress", "MouseClick", "Log", "NoAction"]
    # if action_plan.action_type not in allowed_action_types_for_ref:
    #     is_safe = False
    #     validation_messages.append(f"Invalid action_type: {action_plan.action_type}")
    
    # if action_plan.action_type == "TypeString" and "text" not in action_plan.parameters:
    #     is_safe = False
    #     validation_messages.append("TypeString action missing required 'text' parameter.")
    
    # if action_plan.action_type == "Log" and "message" not in action_plan.parameters:
    #     is_safe = False
    #     validation_messages.append("Log action missing required 'message' parameter.")

    # --- Constraint Enforcement & Safety Validation (Temporarily Disabled for Debugging) ---
    # The agent explicitly sets a safety_check flag.
    # if not action_plan.constraints.get("safety_check", True):
    #     is_safe = False
    #     validation_messages.append("Action plan explicitly marked as unsafe by agent constraints.")
    
    # Example: Blacklist a dangerous action type if not explicitly allowed
    # if action_plan.action_type == "DeleteFiles" and "allow_delete" not in action_plan.constraints: # Example
    #     is_safe = False
    #     validation_messages.append("Action type 'DeleteFiles' is currently blacklisted for safety reasons.")

    # --- Determine Status (Bypassing Safety Checks as per user request) ---
    # All actions are considered ready for execution.
    status = "ready_for_execution"
    actuator_preview = None # No preview needed for actual execution


    return VerifiedActionPlan(
        action_plan=action_plan,
        status=status,
        validation_messages=validation_messages,
        actuator_preview=actuator_preview
    )
