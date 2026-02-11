import pytest
import uuid
from datetime import datetime

from aios.protocols.schema import ActionPlan, AIOSBaseModel, Receipt
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

def test_process_action_plan_invalid_action_type():
    """Tests an action plan with an invalid action type."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="InvalidAction",
        parameters={},
        constraints={"safety_check": True},
        dry_run=False
    )
    
    verified_plan = process_action_plan(action_plan)
    
    assert isinstance(verified_plan, VerifiedActionPlan)
    assert verified_plan.status == "rejected_unsafe"
    assert "Invalid action_type: InvalidAction" in verified_plan.validation_messages[0]

def test_process_action_plan_typestring_missing_param():
    """Tests a TypeString action plan missing the 'text' parameter."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="TypeString",
        parameters={}, # Missing 'text'
        constraints={"safety_check": True},
        dry_run=False
    )
    
    verified_plan = process_action_plan(action_plan)
    
    assert isinstance(verified_plan, VerifiedActionPlan)
    assert verified_plan.status == "rejected_unsafe"
    assert "TypeString action missing required 'text' parameter." in verified_plan.validation_messages[0]

def test_process_action_plan_dangerous_blacklisted_action():
    """Tests a blacklisted dangerous action type."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="DeleteFiles",
        parameters={"path": "C:"},
        constraints={"safety_check": True}, # Agent thinks it's safe
        dry_run=False
    )
    
    verified_plan = process_action_plan(action_plan)
    
    assert isinstance(verified_plan, VerifiedActionPlan)
    assert verified_plan.status == "rejected_unsafe"
    assert "Invalid action_type: DeleteFiles" in verified_plan.validation_messages[0]

