import pytest
import uuid
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from aios.protocols.schema import ActionPlan, Receipt
from aios.protocols.action_protocol import VerifiedActionPlan
from aios.actuators.main_actuator import execute_action

@pytest.fixture
def mock_verified_action_plan():
    """Returns a basic VerifiedActionPlan fixture."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="TypeString",
        parameters={"text": "Hello Test!"},
        constraints={"safety_check": True},
        dry_run=False
    )
    return VerifiedActionPlan(
        action_plan=action_plan,
        status="ready_for_execution",
        validation_messages=[]
    )

def test_execute_action_typestring_success(mock_verified_action_plan):
    """Tests successful execution of a TypeString action."""
    mock_verified_action_plan.action_plan.action_type = "TypeString"
    mock_verified_action_plan.action_plan.parameters = {"text": "Hello World"}
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    # Mock pynput.keyboard.Controller
    with patch('aios.actuators.main_actuator.KeyboardController') as MockKeyboardController:
        mock_keyboard = MockKeyboardController.return_value
        receipt = execute_action(mock_verified_action_plan)
        
        mock_keyboard.type.assert_called_once_with("Hello World")
        assert receipt.status == "success"
        assert "Successfully typed" in receipt.message
        assert receipt.latency_ms > 0

def test_execute_action_log_success(mock_verified_action_plan, capsys):
    """Tests successful execution of a Log action."""
    mock_verified_action_plan.action_plan.action_type = "Log"
    mock_verified_action_plan.action_plan.parameters = {"message": "Test Log Message"}
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    captured = capsys.readouterr()
    assert "Actuator Log (Actual Execution): Test Log Message" in captured.out
    assert receipt.status == "success"
    assert "Successfully logged message" in receipt.message
    assert receipt.latency_ms > 0

def test_execute_action_noaction_success(mock_verified_action_plan):
    """Tests successful execution of a NoAction action."""
    mock_verified_action_plan.action_plan.action_type = "NoAction"
    mock_verified_action_plan.action_plan.parameters = {}
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "success"
    assert "No action was required or taken." in receipt.message
    assert receipt.latency_ms > 0

def test_execute_action_dry_run(mock_verified_action_plan):
    """Tests that action is not executed in dry-run mode."""
    mock_verified_action_plan.action_plan.dry_run = True
    mock_verified_action_plan.status = "dry_run_completed"
    mock_verified_action_plan.actuator_preview = "Would type: 'Dry Run'"

    with patch('aios.actuators.main_actuator.KeyboardController') as MockKeyboardController:
        mock_keyboard = MockKeyboardController.return_value
        receipt = execute_action(mock_verified_action_plan)
        
        mock_keyboard.type.assert_not_called()
        assert receipt.status == "dry_run_success"
        assert "completed successfully in dry-run mode" in receipt.message
        assert receipt.latency_ms > 0

def test_execute_action_rejected_unsafe(mock_verified_action_plan):
    """Tests that action is not executed if rejected unsafe."""
    mock_verified_action_plan.status = "rejected_unsafe"
    mock_verified_action_plan.validation_messages.append("This is unsafe.")

    with patch('aios.actuators.main_actuator.KeyboardController') as MockKeyboardController:
        mock_keyboard = MockKeyboardController.return_value
        receipt = execute_action(mock_verified_action_plan)
        
        mock_keyboard.type.assert_not_called()
        assert receipt.status == "rejected_unsafe"
        assert "Action was rejected by Protocol2 as unsafe." in receipt.message
        assert receipt.latency_ms > 0

def test_execute_action_typestring_missing_text(mock_verified_action_plan):
    """Tests TypeString action with missing 'text' parameter."""
    mock_verified_action_plan.action_plan.action_type = "TypeString"
    mock_verified_action_plan.action_plan.parameters = {} # Missing text
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "failure"
    assert "TypeString action missing 'text' parameter." in receipt.message

def test_execute_action_unknown_action_type(mock_verified_action_plan):
    """Tests an unknown action type."""
    mock_verified_action_plan.action_plan.action_type = "UnknownAction"
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "failure"
    assert "Unknown action type for execution: 'UnknownAction'" in receipt.message
