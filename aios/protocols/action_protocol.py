from __future__ import annotations
from typing import Dict, Any, List
import uuid

from aios.protocols.schema import AIOSBaseModel, ActionPlan, Receipt, TypeStringParameters, KeyPressParameters, MouseClickParameters

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

    # --- Basic Validation (Re-enabled for Iteration 3) ---
    allowed_action_types = ["TypeString", "KeyPress", "MouseClick", "Log", "NoAction"]
    if action_plan.action_type not in allowed_action_types:
        is_safe = False
        validation_messages.append(f"Invalid action_type: {action_plan.action_type}")
    
    # Check parameters for TypeString
    if action_plan.action_type == "TypeString":
        # Check if parameters is a TypeStringParameters instance
        if not isinstance(action_plan.parameters, TypeStringParameters):
            is_safe = False
            validation_messages.append(f"TypeString action requires parameters of type TypeStringParameters, but got {type(action_plan.parameters)}.")
        elif not action_plan.parameters.text: # Check for empty string too
            is_safe = False
            validation_messages.append("TypeString action missing required 'text' parameter or text is empty.")
    
    # Check parameters for KeyPress
    if action_plan.action_type == "KeyPress":
        if not isinstance(action_plan.parameters, KeyPressParameters):
            is_safe = False
            validation_messages.append(f"KeyPress action requires parameters of type KeyPressParameters, but got {type(action_plan.parameters)}.")
        elif not action_plan.parameters.key:
            is_safe = False
            validation_messages.append("KeyPress action missing required 'key' parameter.")

    # Check parameters for MouseClick
    if action_plan.action_type == "MouseClick":
        if not isinstance(action_plan.parameters, MouseClickParameters):
            is_safe = False
            validation_messages.append(f"MouseClick action requires parameters of type MouseClickParameters, but got {type(action_plan.parameters)}.")
        # Basic check for x and y
        elif not (hasattr(action_plan.parameters, 'x') and hasattr(action_plan.parameters, 'y')):
             is_safe = False
             validation_messages.append("MouseClick action missing required 'x' or 'y' parameter.")

    # Check parameters for Log
    if action_plan.action_type == "Log" and "message" not in action_plan.parameters: # Log uses Dict[str, Any] currently
        is_safe = False
        validation_messages.append("Log action missing required 'message' parameter.")

    # --- Constraint Enforcement & Safety Validation (Re-enabled) ---
    # The agent explicitly sets a safety_check flag.
    if not action_plan.constraints.get("safety_check", True):
        is_safe = False
        validation_messages.append("Action plan explicitly marked as unsafe by agent constraints.")
    
    # Example: Blacklist a dangerous action type if not explicitly allowed
    # (Future: Implement more sophisticated blacklisting)
    if action_plan.action_type == "DeleteFiles": # Example of a potentially unsafe action
        is_safe = False
        validation_messages.append("Action type 'DeleteFiles' is currently blacklisted for safety reasons.")

    # --- Determine Status ---
    if not is_safe:
        status = "rejected_unsafe"
        actuator_preview = "Action rejected due to safety violations."
    elif action_plan.dry_run: # dry_run should be False by default now, so this path should be rare
        status = "dry_run_completed"
        # Simulate what the actuator would do without actually doing it
        if action_plan.action_type == "TypeString":
            actuator_preview = f"Would type: '{action_plan.parameters.text}'" # Access .text directly
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
