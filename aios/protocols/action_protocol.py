from __future__ import annotations
import re
from typing import Dict, Any, List, Type
from pydantic import BaseModel, ValidationError

from aios.protocols.schema import (
    AIOSBaseModel,
    ActionPlan,
    TypeStringParameters,
    KeyPressParameters,
    MouseClickParameters,
    NoActionParameters,
    LogParameters
)

class VerifiedActionPlan(AIOSBaseModel):
    """
    Represents an ActionPlan after Protocol2 processing, including validation status
    and a normalized parameters object.
    """
    action_plan: ActionPlan
    status: str
    validation_messages: List[str] = []
    actuator_preview: str | None = None

# Map action types to their corresponding Pydantic parameter models
ACTION_PARAM_MAP: Dict[str, Type[BaseModel]] = {
    "TypeString": TypeStringParameters,
    "KeyPress": KeyPressParameters,
    "MouseClick": MouseClickParameters,
    "Log": LogParameters,
    "NoAction": NoActionParameters,
}

def _validate_typestring_params(params: TypeStringParameters, validation_messages: List[str]):
    # Prevent typing of known sensitive patterns
    sensitive_patterns = [r"sk-", r"AKIA", r"A3T", r"AGPA", r"ASIA"] # Common API key prefixes
    for pattern in sensitive_patterns:
        if re.search(pattern, params.text, re.IGNORECASE):
            validation_messages.append(f"Safety violation: TypeString contains sensitive pattern '{pattern}'.")
            break
    
    # Max length check to prevent excessive typing/spam
    if len(params.text) > 200:
        validation_messages.append("Safety violation: TypeString exceeds maximum allowed length (200 characters).")

def _validate_keypress_params(params: KeyPressParameters, validation_messages: List[str]):
    # Allowlist for safe key combinations
    allowed_keys = {
        "enter", "tab", "space", "backspace", "delete", "esc",
        "up", "down", "left", "right",
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
        "a", "c", "v", "n", "s", "w", "z", "y" # For Ctrl+A,C,V,N,S,W,Z,Y etc.
    }
    allowed_modifiers = {"ctrl", "alt", "shift", "win"}

    if params.key.lower() not in allowed_keys and len(params.key) == 1: # Allow any single character for typing, but restrict special keys
        validation_messages.append(f"Safety violation: KeyPress uses disallowed key '{params.key}'.")

    for mod in params.modifiers:
        if mod.lower() not in allowed_modifiers:
            validation_messages.append(f"Safety violation: KeyPress uses disallowed modifier '{mod}'.")

    # Specific common safe combinations
    safe_combinations = [
        ({"ctrl"}, "a"), ({"ctrl"}, "c"), ({"ctrl"}, "v"), ({"ctrl"}, "n"), ({"ctrl"}, "s"), ({"ctrl"}, "w"),
        ({"alt"}, "f4"), ({"alt"}, "tab"), ({"alt"}, "n"), ({"alt"}, "y") # Alt+N for "Don't Save", Alt+Y for "Yes"
    ]
    current_combination = (set([m.lower() for m in params.modifiers]), params.key.lower())
    # Note: this check is not exhaustive for all allowed single keys, just for explicit combinations
    # The individual key/modifier checks above cover general cases.

def _validate_mouseclick_params(params: MouseClickParameters, validation_messages: List[str]):
    # Basic bounds check (e.g., prevent clicks far outside screen, though screen size is unknown here)
    if not (0 <= params.x < 3000 and 0 <= params.y < 2000): # Arbitrary reasonable screen bounds
        validation_messages.append(f"Safety violation: MouseClick coordinates ({params.x}, {params.y}) are outside reasonable screen bounds.")
    
    # Rate limit check can be implemented at the actuator level or by tracking recent actions in TaskState
    # For now, it's not a direct parameter validation.

def process_action_plan(action_plan: ActionPlan) -> VerifiedActionPlan:
    """
    Processes and validates an ActionPlan from the Agent.

    It normalizes the parameters dict into a validated Pydantic model,
    enforces safety checks, and returns a VerifiedActionPlan ready for
    the actuator.
    """
    params_class = ACTION_PARAM_MAP.get(action_plan.action_type)
    validation_messages: List[str] = []
    
    if not params_class:
        validation_messages.append(f"Unknown action_type: '{action_plan.action_type}'.")
        return VerifiedActionPlan(
            action_plan=action_plan,
            status="rejected_unsafe",
            validation_messages=validation_messages
        )

    try:
        validated_params = params_class.model_validate(action_plan.parameters)
        
        # --- Apply Safety Checks ---
        if action_plan.action_type == "TypeString":
            _validate_typestring_params(validated_params, validation_messages)
        elif action_plan.action_type == "KeyPress":
            _validate_keypress_params(validated_params, validation_messages)
        elif action_plan.action_type == "MouseClick":
            _validate_mouseclick_params(validated_params, validation_messages)
        # Add checks for other action types as they are introduced

        if validation_messages:
            return VerifiedActionPlan(
                action_plan=action_plan,
                status="rejected_unsafe",
                validation_messages=validation_messages
            )

        # Create a new, validated action plan with the Pydantic model as parameters
        validated_action_plan = action_plan.model_copy(
            update={"parameters": validated_params}
        )

        status = "ready_for_execution"
        actuator_preview = None
        if action_plan.dry_run:
            status = "dry_run_completed"
            if validated_params:
                actuator_preview = f"Would execute {action_plan.action_type} with params: {validated_params.model_dump_json()}"
            else:
                actuator_preview = f"Would execute {action_plan.action_type}."
        
        return VerifiedActionPlan(
            action_plan=validated_action_plan,
            status=status,
            actuator_preview=actuator_preview,
            validation_messages=validation_messages
        )

    except ValidationError as e:
        validation_messages.append(f"Parameter validation failed for '{action_plan.action_type}': {e}")
        return VerifiedActionPlan(
            action_plan=action_plan,
            status="rejected_unsafe",
            validation_messages=validation_messages
        )
    except Exception as e:
        validation_messages.append(f"An unexpected error occurred during action plan processing: {e}")
        return VerifiedActionPlan(
            action_plan=action_plan,
            status="rejected_unsafe",
            validation_messages=validation_messages
        )
