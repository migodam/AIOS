import pytest
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
from requests import HTTPError

from aios.protocols.schema import RawSignal, ObservationEvent, ScreenshotData, UIATreeData, LogData
from aios.protocols.llm_connector import call_llm_api, LLM_API_ENDPOINT

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
mock_log_signal = RawSignal(
    observer_id="test_log",
    artifact_path="/tmp/test_log.log",
    artifact_hash="hash_log",
    data=LogData(log_source="test_file.log", new_lines=["line1", "line2"])
)

def test_call_llm_api_mock_mode_success():
    """Test call_llm_api in mock mode, success path."""
    raw_signals = [mock_screenshot_signal, mock_uia_signal]
    
    observation_event = call_llm_api(raw_signals, use_mock=True)
    
    assert isinstance(observation_event, ObservationEvent)
    assert observation_event.raw_signals == raw_signals
    assert "Desktop screenshot" in observation_event.ui_state_summary
    assert "Test App" in observation_event.ui_state_summary
    assert observation_event.potential_intent == "Waiting for user input." # Corrected expectation
    assert observation_event.environment_state_summary == "System appears normal."

def test_call_llm_api_mock_mode_with_log_signal():
    """Test mock mode with a log signal present."""
    raw_signals = [mock_log_signal]
    observation_event = call_llm_api(raw_signals, use_mock=True)
    assert "Recent logs show activity in test_file.log." in observation_event.environment_state_summary

@patch('requests.post')
def test_call_llm_api_live_mode_success(mock_post):
    """Test call_llm_api in live mode, success path."""
    mock_response_json = {
        "ui_state_summary": "LLM says: UI is good.",
        "environment_state_summary": "LLM says: Env is healthy.",
        "potential_intent": "LLM says: Intent is clear."
    }
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = mock_response_json
    mock_post.return_value = mock_response

    raw_signals = [mock_screenshot_signal]
    observation_event = call_llm_api(raw_signals, use_mock=False)

    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == LLM_API_ENDPOINT
    assert isinstance(observation_event, ObservationEvent)
    assert observation_event.ui_state_summary == mock_response_json["ui_state_summary"]
    assert observation_event.environment_state_summary == mock_response_json["environment_state_summary"]
    assert observation_event.potential_intent == mock_response_json["potential_intent"]

@patch('requests.post')
def test_call_llm_api_live_mode_api_failure(mock_post):
    """Test call_llm_api in live mode, API failure."""
    mock_post.side_effect = HTTPError("Mock HTTP Error")

    raw_signals = [mock_screenshot_signal]
    with pytest.raises(RuntimeError, match="LLM API call failed"):
        call_llm_api(raw_signals, use_mock=False)
    
    mock_post.assert_called_once()

@patch('requests.post')
def test_call_llm_api_live_mode_invalid_response(mock_post):
    """Test call_llm_api in live mode, invalid LLM response (schema validation)."""
    mock_response_json = {
        "ui_state_summary": "LLM says: UI is good.",
        # Missing required 'potential_intent'
    }
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = mock_response_json
    mock_post.return_value = mock_response

    raw_signals = [mock_screenshot_signal]
    with pytest.raises(RuntimeError, match="LLM response invalid"):
        call_llm_api(raw_signals, use_mock=False)
    
    mock_post.assert_called_once()

