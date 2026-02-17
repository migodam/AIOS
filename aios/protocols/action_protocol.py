from __future__ import annotations
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

def process_action_plan(action_plan: ActionPlan) -> VerifiedActionPlan:
    """
    Processes and validates an ActionPlan from the Agent.

    It normalizes the parameters dict into a validated Pydantic model,
    enforces safety checks, and returns a VerifiedActionPlan ready for
    the actuator.
    """
    params_class = ACTION_PARAM_MAP.get(action_plan.action_type)
    
    if not params_class:
        return VerifiedActionPlan(
            action_plan=action_plan,
            status="rejected_unsafe",
            validation_messages=[f"Unknown action_type: '{action_plan.action_type}'"]
        )

    try:
        # Validate and normalize the parameters dictionary
        validated_params = params_class.model_validate(action_plan.parameters)
        
        # Create a new, validated action plan with the Pydantic model as parameters
        validated_action_plan = action_plan.model_copy(
            update={"parameters": validated_params}
        )

        # (Future) Add more sophisticated safety checks here if needed

        status = "ready_for_execution"
        if action_plan.dry_run:
            status = "dry_run_completed"
            actuator_preview = f"Would execute {action_plan.action_type} with params: {validated_params.model_dump_json()}"
        
        return VerifiedActionPlan(
            action_plan=validated_action_plan,
            status=status,
            actuator_preview=actuator_preview
        )

    except ValidationError as e:
        # Validation failed, reject the action
        return VerifiedActionPlan(
            action_plan=action_plan,
            status="rejected_unsafe",
            validation_messages=[f"Parameter validation failed for '{action_plan.action_type}': {e}"]
        )
    except Exception as e:
        # Catch any other unexpected errors during processing
        return VerifiedActionPlan(
            action_plan=action_plan,
            status="rejected_unsafe",
            validation_messages=[f"An unexpected error occurred during action plan processing: {e}"]
        )
