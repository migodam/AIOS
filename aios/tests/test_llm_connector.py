import pytest
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import json
import os # Added for path manipulation

from aios.protocols.schema import RawSignal, ObservationEvent, ScreenshotData, UIATreeData, LogData
from aios.protocols.llm_connector import request_protocol_llm_observation, request_core_agent_llm_action, _construct_prompt_from_raw_signals, _load_prompt_from_file
from aios.llm.llm_client import LLMClient
from aios.protocols.schema import ProtocolLLMOutput, ActionPlan

# Mock RawSignal data for testing
mock_screenshot_signal = RawSignal(
    observer_id="test_screenshot",
    artifact_path="/tmp/test_ss.png",
    artifact_hash="hash_ss",
    data=ScreenshotData(screen_size=(100, 100))
)
mock_uia_signal = RawSignal(
    observer_id="test_uia",
    artifact_path="/tmp/test_uia.json",
    artifact_hash="hash_uia",
    data=UIATreeData(focused_window_title="Test App", tree_structure={"root": "mock"})
)
mock_uia_notepad_signal = RawSignal(
    observer_id="test_uia_notepad",
    artifact_path="/tmp/test_uia_notepad.json",
    artifact_hash="hash_uia_notepad",
    data=UIATreeData(focused_window_title="Untitled - Notepad", tree_structure={"class_name": "Notepad", "children": []})
)
mock_log_signal = RawSignal(
    observer_id="test_log",
    artifact_path="/tmp/test_log.log",
    artifact_hash="hash_log",
    data=LogData(log_source="test_file.log", new_lines=["line1", "line2"])
)

# Mock API Key for testing
TEST_API_KEY = "test-api-key"

@pytest.fixture
def mock_llm_client():
    """Mocks the LLMClient for isolated testing."""
    with patch('aios.protocols.llm_connector.LLMClient') as MockLLMClient:
        mock_instance = MockLLMClient.return_value
        yield mock_instance

@pytest.fixture
def mock_protocol_llm_prompt():
    """Mocks the content of the protocol LLM prompt file."""
    with patch("builtins.open", mock_open(read_data="You are ProtocolLLM. Your task is to convert raw observation signals into structured ObservationEvent JSON.")) as m_open:
        with patch("os.path.dirname", return_value="/mock/aios/protocols"): # Mock the base path
            with patch("os.path.join", side_effect=lambda a,b: f"{a}/{b}"): # Mock path join for simplicity
                yield m_open

@pytest.fixture
def mock_core_llm_prompt():
    """Mocks the content of the core LLM prompt file."""
    with patch("builtins.open", mock_open(read_data="You are CoreAgentLLM. You receive observations and memory to decide actions.")) as m_open:
        with patch("os.path.dirname", return_value="/mock/aios/protocols"):
            with patch("os.path.join", side_effect=lambda a,b: f"{a}/{b}"):
                yield m_open

# --- Tests ---

# --- Tests for _load_prompt_from_file ---
def test_load_prompt_from_file(mock_protocol_llm_prompt):
    """Test loading a prompt from a file."""
    prompt_content = _load_prompt_from_file("prompts/protocol_llm_prompt.txt")
    assert "You are ProtocolLLM" in prompt_content
    mock_protocol_llm_prompt.assert_called_once_with(os.path.join("/mock/aios", "prompts/protocol_llm_prompt.txt"), 'r', encoding='utf-8')

# --- Tests for request_protocol_llm_observation ---
def test_request_protocol_llm_observation_success(mock_llm_client, mock_protocol_llm_prompt):
    """Test request_protocol_llm_observation success path."""
    mock_llm_client.generate.return_value = {
        "intent": "Test Intent",
        "ui_state_summary": "Test UI Summary",
        "confidence": 0.95
    }
    
    raw_signals = [mock_screenshot_signal]
    observation_event = request_protocol_llm_observation(
        raw_signals=raw_signals,
        llm_api_key=TEST_API_KEY,
        protocol_llm_prompt_filename="protocol_llm_prompt.txt",
        user_instruction="User instruction test"
    )

    mock_llm_client.generate.assert_called_once()
    args, kwargs = mock_llm_client.generate.call_args
    assert kwargs['system_prompt'] == "You are ProtocolLLM. Your task is to convert raw observation signals into structured ObservationEvent JSON."
    assert "User instruction test" in kwargs['user_prompt']
    assert observation_event.potential_intent == "Test Intent"
    assert observation_event.ui_state_summary == "Test UI Summary"
    assert observation_event.raw_signals == raw_signals
    assert isinstance(observation_event, ObservationEvent)

def test_request_protocol_llm_observation_invalid_response_raises_error(mock_llm_client, mock_protocol_llm_prompt):
    """Test request_protocol_llm_observation with invalid LLM response."""
    mock_llm_client.generate.return_value = {
        "intent": "Test Intent",
        "ui_state_summary": "Test UI Summary",
        # Missing confidence
    }
    raw_signals = [mock_screenshot_signal]
    with pytest.raises(RuntimeError, match="LLM response invalid"):
        request_protocol_llm_observation(
            raw_signals=raw_signals,
            llm_api_key=TEST_API_KEY,
            protocol_llm_prompt_filename="protocol_llm_prompt.txt"
        )

# --- Tests for request_core_agent_llm_action ---
def test_request_core_agent_llm_action_success(mock_llm_client, mock_core_llm_prompt):
    """Test request_core_agent_llm_action success path."""
    mock_action_plan_id = str(uuid.uuid4())
    mock_observation_id = str(uuid.uuid4())
    mock_llm_client.generate.return_value = {
        "action_id": mock_action_plan_id,
        "origin_observation_id": mock_observation_id,
        "action_type": "KeyPress",
        "parameters": {"key": "enter"},
        "constraints": {},
        "dry_run": False
    }
    
    observation_event = ObservationEvent(
        observation_id=mock_observation_id,
        raw_signals=[],
        ui_state_summary="some ui",
        environment_state_summary="some env",
        potential_intent="some intent"
    )
    graph_memory_summary = "Graph summary here."
    user_instruction = "Do something."

    action_plan = request_core_agent_llm_action(
        observation_event=observation_event,
        graph_memory_summary=graph_memory_summary,
        user_instruction=user_instruction,
        llm_api_key=TEST_API_KEY,
        core_llm_prompt_filename="core_llm_prompt.txt"
    )

    mock_llm_client.generate.assert_called_once()
    args, kwargs = mock_llm_client.generate.call_args
    assert kwargs['system_prompt'] == "You are CoreAgentLLM. You receive observations and memory to decide actions."
    assert "Graph summary here." in kwargs['user_prompt']
    assert "Do something." in kwargs['user_prompt']
    assert action_plan.action_type == "KeyPress"
    assert action_plan.action_id == mock_action_plan_id
    assert isinstance(action_plan, ActionPlan)

def test_request_core_agent_llm_action_invalid_response_raises_error(mock_llm_client, mock_core_llm_prompt):
    """Test request_core_agent_llm_action with invalid LLM response."""
    mock_llm_client.generate.return_value = {
        "action_id": str(uuid.uuid4()),
        "origin_observation_id": str(uuid.uuid4()),
        "action_type": "InvalidType", # Invalid action type
        "parameters": {},
        "constraints": {},
        "dry_run": False
    }
    observation_event = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="some ui",
        environment_state_summary="some env",
        potential_intent="some intent"
    )
    with pytest.raises(RuntimeError, match="LLM response invalid"):
        request_core_agent_llm_action(
            observation_event=observation_event,
            graph_memory_summary="summary",
            user_instruction="instruction",
            llm_api_key=TEST_API_KEY,
            core_llm_prompt_filename="core_llm_prompt.txt"
        )
