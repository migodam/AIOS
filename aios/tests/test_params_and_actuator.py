import pytest
import uuid
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
import dataclasses
from pynput.keyboard import Key # ADDED Key for assertions

# Import components for testing
from aios.protocols.schema import ActionPlan, Receipt, TypeStringParameters, KeyPressParameters, MouseClickParameters, AIOSBaseModel
from aios.protocols.action_protocol import VerifiedActionPlan
from aios.actuators.main_actuator import execute_action
from aios.utils.params import normalize_params, desensitize_api_key

# --- Fixtures ---
@pytest.fixture
def mock_verified_action_plan():
    """Returns a basic VerifiedActionPlan fixture."""
    action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=str(uuid.uuid4()),
        action_type="NoAction", # Default to NoAction
        parameters={},
        constraints={"safety_check": True},
        dry_run=False
    )
    return VerifiedActionPlan(
        action_plan=action_plan,
        status="ready_for_execution",
        validation_messages=[]
    )

@pytest.fixture
def mock_keyboard_controller():
    """Mocks pynput.keyboard.Controller."""
    with patch('aios.actuators.main_actuator.KeyboardController') as MockKeyboardController:
        yield MockKeyboardController.return_value

@pytest.fixture
def mock_mouse_controller():
    """Mocks pynput.mouse.Controller."""
    with patch('aios.actuators.main_actuator.MouseController') as MockMouseController:
        yield MockMouseController.return_value

# --- Tests for normalize_params ---
def test_normalize_params_none_input():
    """Test normalize_params with None input."""
    assert normalize_params(None) == {}

def test_normalize_params_dict_input():
    """Test normalize_params with dict input."""
    input_dict = {"key": "value", "num": 123}
    assert normalize_params(input_dict) == input_dict

def test_normalize_params_pydantic_v2_input():
    """Test normalize_params with Pydantic v2 model input."""
    class TestPydanticV2(AIOSBaseModel):
        field_str: str = "hello"
        field_int: int = 123

    pydantic_obj = TestPydanticV2()
    expected_dict = {"timestamp": pydantic_obj.timestamp.isoformat(timespec='milliseconds') + 'Z', "version": 1, "field_str": "hello", "field_int": 123}
    # Pydantic model_dump returns ISO formatted datetime string.
    normalized = normalize_params(pydantic_obj)
    # Compare with expected dict after converting timestamp to isoformat
    assert normalized['field_str'] == expected_dict['field_str']
    assert normalized['field_int'] == expected_dict['field_int']
    assert 'timestamp' in normalized

def test_normalize_params_dataclass_input():
    """Test normalize_params with dataclass input."""
    @dataclasses.dataclass
    class TestDataclass:
        name: str
        value: int

    dataclass_obj = TestDataclass(name="test", value=42)
    assert normalize_params(dataclass_obj) == {"name": "test", "value": 42}

def test_normalize_params_unsupported_type():
    """Test normalize_params with an unsupported object type."""
    with pytest.raises(TypeError, match="Unsupported parameter type for normalization: <class 'list'>"):
        normalize_params([1, 2, 3])

# --- Tests for Actuator KeyPress parameter handling ---
def test_actuator_keypress_params_model_no_crash(mock_verified_action_plan, mock_keyboard_controller):
    """
    Test KeyPress action with KeyPressParameters model (Pydantic object) doesn't crash.
    This simulates LLM directly outputting a Pydantic-like object for parameters.
    """
    mock_verified_action_plan.action_plan.action_type = "KeyPress"
    mock_verified_action_plan.action_plan.parameters = KeyPressParameters(key="space", modifiers=[])
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "success"
    mock_keyboard_controller.press.assert_any_call(Key.space)
    mock_keyboard_controller.release.assert_any_call(Key.space)

def test_actuator_keypress_string_hotkey_no_crash(mock_verified_action_plan, mock_keyboard_controller):
    """
    Test KeyPress action with hotkey string (e.g., "win+r") doesn't crash.
    """
    mock_verified_action_plan.action_plan.action_type = "KeyPress"
    mock_verified_action_plan.action_plan.parameters = {"hotkey": "win+r"}
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "success"
    mock_keyboard_controller.press.assert_any_call(Key.cmd)
    mock_keyboard_controller.type.assert_called_once_with('r') # Should use type for character 'r'
    mock_keyboard_controller.release.assert_any_call(Key.cmd)

def test_actuator_keypress_keys_list_no_crash(mock_verified_action_plan, mock_keyboard_controller):
    """
    Test KeyPress action with 'keys' list (e.g., ["ctrl", "c"]) doesn't crash.
    """
    mock_verified_action_plan.action_plan.action_type = "KeyPress"
    mock_verified_action_plan.action_plan.parameters = {"keys": ["ctrl", "c"]}
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "success"
    mock_keyboard_controller.press.assert_any_call(Key.ctrl)
    mock_keyboard_controller.type.assert_called_once_with('c') # Type for single character key without modifier
    mock_keyboard_controller.release.assert_any_call(Key.ctrl)

def test_actuator_keypress_missing_params_fails_gracefully(mock_verified_action_plan):
    """
    Test KeyPress action with missing parameters results in failed receipt.
    """
    mock_verified_action_plan.action_plan.action_type = "KeyPress"
    mock_verified_action_plan.action_plan.parameters = {} # Empty parameters
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "failed"
    assert "missing required 'keys', 'key', or 'hotkey' parameter" in receipt.message
    assert receipt.error["type"] == "Parameter Error"
    assert receipt.error["retryable"] is False

def test_actuator_mouseclick_params_model_no_crash(mock_verified_action_plan, mock_mouse_controller):
    """
    Test MouseClick action with MouseClickParameters model doesn't crash.
    """
    mock_verified_action_plan.action_plan.action_type = "MouseClick"
    mock_verified_action_plan.action_plan.parameters = MouseClickParameters(x=100, y=200, button="left", clicks=1)
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "success"
    mock_mouse_controller.position = (100, 200) # Assert position set
    mock_mouse_controller.click.assert_called_once()
    assert receipt.latency_ms > 0

def test_actuator_mouseclick_missing_coords_fails_gracefully(mock_verified_action_plan):
    """
    Test MouseClick action with missing coordinates results in failed receipt.
    """
    mock_verified_action_plan.action_plan.action_type = "MouseClick"
    mock_verified_action_plan.action_plan.parameters = {"button": "left"} # Missing x, y
    mock_verified_action_plan.status = "ready_for_execution"
    mock_verified_action_plan.action_plan.dry_run = False

    receipt = execute_action(mock_verified_action_plan)
    
    assert receipt.status == "failed"
    assert "MouseClick action missing required 'x' or 'y' parameter" in receipt.message
    assert receipt.error["type"] == "Parameter Error"
    assert receipt.error["retryable"] is False

# --- Tests for API Key Leakage ---
def test_desensitize_api_key_function():
    """Test the desensitize_api_key utility function."""
    assert desensitize_api_key("sk-abcdef1234567890") == "sk-***"
    assert desensitize_api_key("my_key_is_sk-123456") == "my_key_is_sk-***"
    assert desensitize_api_key("sk-") == "sk-***" # Edge case
    assert desensitize_api_key("not_an_api_key") == "not_an_api_key"
    assert desensitize_api_key(None) is None
    assert desensitize_api_key("sk-1234") == "sk-***"
    assert desensitize_api_key("sk-12345") == "sk-***" 

@patch('aios_demo.run_aios_cycle')
def test_no_key_leak_in_cli_execution_log(mock_run_aios_cycle, capsys):
    """
    Test that the LLM API key is desensitized in the GUI's "Executing" log line.
    This requires simulating the GUI's subprocess launch logic.
    \"\"\"
    from gui import _run_aios_in_thread # Import the helper function directly
    mock_gui = MagicMock()
    mock_gui.log_status = MagicMock()

    test_api_key = "sk-test12345abcdefg"
    user_instruction = "test instruction"

    # Mock subprocess.Popen to prevent actual execution, just capture command
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value.stdout.readline.side_effect = ['line1', ''] # Simulate some output
        mock_popen.return_value.stdout.close.return_value = None
        mock_popen.return_value.wait.return_value = 0

        _run_aios_in_thread(mock_gui, user_instruction, test_api_key, MagicMock())
        
        # Check the log_status call that displays the executing command
        # This will be the third call to log_status in _run_aios_in_thread
        # 1: "AIOS Demo started..."
        # 2: "LLM API Key: ***"
        # 3: "Executing: python aios_demo.py --user_instruction ... --llm_api_key sk-test***"
        execution_log_call = mock_gui.log_status.call_args_list[0]
        
        assert "Executing:" in execution_log_call.args[0]
        assert test_api_key not in execution_log_call.args[0]
        assert "sk-***" in execution_log_call.args[0]
    
# This test assumes gui.py's log_status is called for "LLM API Key: "
def test_no_key_leak_in_gui_api_key_status(capsys):
    \"\"\"
    Test that the LLM API key is desensitized in the GUI's "LLM API Key" status log.
    This requires simulating the run_aios_demo call in GUI.
    \"\"\"
    from gui import AIOSGui # Import the class directly
    root = MagicMock()
    mock_gui = AIOSGui(root)
    
    mock_gui.api_key_entry = MagicMock()
    mock_gui.api_key_entry.get.return_value = "sk-testapi123"
    mock_gui.instruction_text = MagicMock() # Mock the ScrolledText widget
    mock_gui.instruction_text.get.return_value = "do something"
    
    mock_gui.log_status = MagicMock() # Mock the log_status method
    
    with patch('threading.Thread') as MockThread:
        mock_gui.run_aios_demo()

        # Check the log_status call that logs the API key
        api_key_log_call = mock_gui.log_status.call_args_list[1] # Second call
        assert "LLM API Key: sk-***" in api_key_log_call.args[0]
        assert "sk-testapi123" not in api_key_log_call.args[0]
"""