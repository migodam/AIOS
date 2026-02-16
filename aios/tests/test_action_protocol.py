import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError # ADDED

from aios.protocols.schema import ActionPlan, AIOSBaseModel, Receipt, TypeStringParameters, KeyPressParameters, MouseClickParameters
from aios.protocols.action_protocol import process_action_plan, VerifiedActionPlan

def test_process_action_plan_typestring_success():
    """Tests successful processing of a TypeString action plan."""
    action_id = str(uuid.uuid4())
    obs_id = str(uuid.uuid4())
    action_plan = ActionPlan(
        action_id=action_id,
        origin_observation_id=obs_id,
        action_type="TypeString",
        parameters={"text": "Hello AIOS!"},
        constraints={"safety_check": True},
        dry_run=True
    )
    
    verified_plan = process_action_plan(action_plan)
    
    assert isinstance(verified_plan, VerifiedActionPlan)
    assert verified_plan.action_plan.action_id == action_id
    assert verified_plan.status == "dry_run_completed"
    assert "Would type: 'Hello AIOS!'" in verified_plan.actuator_preview
    assert len(verified_plan.validation_messages) == 0

def test_process_action_plan_log_success():
    """Tests successful processing of a Log action plan."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="Log",
        parameters={"message": "System status update."},
        constraints={"safety_check": True},
        dry_run=False
    )
    
    verified_plan = process_action_plan(action_plan)
    
    assert isinstance(verified_plan, VerifiedActionPlan)
    assert verified_plan.action_plan.action_type == "Log"
    assert verified_plan.status == "ready_for_execution"
    assert verified_plan.actuator_preview is None # No preview for actual execution
    assert len(verified_plan.validation_messages) == 0

def test_process_action_plan_rejected_unsafe():
    """Tests an action plan rejected due to explicit unsafety."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="TypeString",
        parameters={"text": "Dangerous command"},
        constraints={"safety_check": False}, # Explicitly unsafe
        dry_run=False
    )
    
    verified_plan = process_action_plan(action_plan)
    
    assert isinstance(verified_plan, VerifiedActionPlan)
    assert verified_plan.status == "rejected_unsafe"
    assert "Action plan explicitly marked as unsafe" in verified_plan.validation_messages[0]
    assert "rejected due to safety violations" in verified_plan.actuator_preview

def test_action_plan_creation_invalid_action_type_raises_validation_error():
    """Tests that creating an ActionPlan with an invalid action type raises ValidationError."""
    with pytest.raises(ValidationError, match="Input should be 'TypeString'"): # Match part of the expected message
        ActionPlan(
            action_id=str(uuid.uuid4()),
            origin_observation_id=str(uuid.uuid4()),
            action_type="InvalidAction", # Type-checker already flags this
            parameters={},
            constraints={"safety_check": True},
            dry_run=False
        )


def test_process_action_plan_typestring_missing_param():
    """Tests a TypeString action plan with TypeStringParameters missing the 'text' attribute."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="TypeString",
        parameters=TypeStringParameters(text=""), # Empty text, which is caught by validation
        constraints={"safety_check": True},
        dry_run=False
    )
    
    verified_plan = process_action_plan(action_plan)
    
    assert isinstance(verified_plan, VerifiedActionPlan)
    assert verified_plan.status == "rejected_unsafe"
    assert "TypeString action missing required 'text' parameter or text is empty." in verified_plan.validation_messages[0]

def test_action_plan_creation_dangerous_blacklisted_action_raises_validation_error():
    """Tests that creating an ActionPlan with a blacklisted action type raises ValidationError."""
    with pytest.raises(ValidationError, match="Input should be 'TypeString'"): # Match part of the expected message
        ActionPlan(
            action_id=str(uuid.uuid4()),
            origin_observation_id=str(uuid.uuid4()),
            action_type="DeleteFiles", # Type-checker already flags this
            parameters={"path": "C:"},
            constraints={"safety_check": True}, # Agent thinks it's safe
            dry_run=False
        )


