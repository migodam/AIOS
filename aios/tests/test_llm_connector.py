import pytest
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
from requests import HTTPError
import subprocess
import time
import requests
import os
import sys

from aios.protocols.schema import RawSignal, ObservationEvent, ScreenshotData, UIATreeData, LogData
from aios.protocols import llm_connector # Import the module itself

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

# --- Fixture for Mock LLM Server ---
@pytest.fixture(scope="module")
def mock_llm_server():
    """Starts and stops the mock LLM server for module-scoped tests."""
    # Ensure Flask is installed in the test environment
    try:
        import flask
    except ImportError:
        pytest.skip("Flask not installed, skipping mock LLM server tests.")

    # Determine the path to the mock server script
    server_script_path = Path(__file__).parent.parent / "utils" / "mock_llm_server.py"
    if not server_script_path.exists():
        pytest.fail(f"Mock LLM server script not found at {server_script_path}")

    # Use the current Python executable from the virtual environment
    python_executable = sys.executable

    # Start the server as a subprocess
    print(f"\nStarting mock LLM server from: {server_script_path}")
    process = subprocess.Popen(
        [python_executable, "-m", "aios.utils.mock_llm_server"],
        cwd=Path(__file__).parent.parent.parent, # Set CWD to project root for module import
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True # Decode stdout/stderr as text
    )

    # Wait for the server to start
    server_ready = False
    start_time = time.time()
    while not server_ready and (time.time() - start_time < 10): # 10-second timeout
        try:
            # Pinging a known endpoint like "/" usually works for Flask
            response = requests.get(llm_connector.LLM_API_ENDPOINT.replace("/v1/chat/completions", "/"), timeout=1)
            if response.status_code == 200:
                print("Mock LLM server is ready.")
                server_ready = True
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
        except Exception as e:
            print(f"Error checking server readiness: {e}")
            time.sleep(0.5)

    if not server_ready:
        process.terminate()
        process.wait(timeout=2) # Give it a moment to terminate
        stdout, stderr = process.communicate()
        pytest.fail(
            f"Mock LLM server failed to start within 10 seconds. "
            f"Stdout: {stdout}\nStderr: {stderr}"
        )

    yield # Tests run here

    # Stop the server
    print("\nStopping mock LLM server.")
    process.terminate()
    try:
        process.wait(timeout=5) # Wait for server to terminate
    except subprocess.TimeoutExpired:
        print("Mock LLM server did not terminate gracefully, killing it.")
        process.kill()
        process.wait() # Ensure it's killed

    stdout, stderr = process.communicate()
    if stdout:
        print(f"Mock LLM Server Stdout: \n{stdout}")
    if stderr:
        print(f"Mock LLM Server Stderr: \n{stderr}")

# --- Tests ---

def test_call_llm_api_mock_mode_success():
    """Test call_llm_api in mock mode, success path."""
    raw_signals = [mock_screenshot_signal, mock_uia_signal]
    observation_event = llm_connector.call_llm_api(raw_signals, use_mock=True)
    assert observation_event.raw_signals == raw_signals
    assert "Desktop screenshot" in observation_event.ui_state_summary
    assert "Test App" in observation_event.ui_state_summary
    assert observation_event.potential_intent == "Waiting for user instructions."
    assert observation_event.environment_state_summary == "System appears normal."

def test_call_llm_api_mock_mode_with_log_signal():
    """Test mock mode with a log signal present."""
    raw_signals = [mock_log_signal]
    observation_event = llm_connector.call_llm_api(raw_signals, use_mock=True)
    assert "Recent logs show activity in test_file.log." in observation_event.environment_state_summary

def test_call_llm_api_mock_mode_notepad_detection():
    """Test mock mode with Notepad detected in UIA signal."""
    raw_signals = [mock_uia_notepad_signal]
    observation_event = llm_connector.call_llm_api(raw_signals, use_mock=True)
    assert "Untitled - Notepad" in observation_event.ui_state_summary
    assert observation_event.potential_intent == "Preparing to type."


@patch('requests.post')
def test_call_llm_api_live_mode_success(mock_post):
    """Test call_llm_api in live mode, success path (mocking requests for isolation)."""
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
    observation_event = llm_connector.call_llm_api(raw_signals, user_instruction="", use_mock=False)

    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == llm_connector.LLM_API_ENDPOINT
    assert isinstance(observation_event, ObservationEvent)
    assert observation_event.ui_state_summary == mock_response_json["ui_state_summary"]
    assert observation_event.environment_state_summary == mock_response_json["environment_state_summary"]
    assert observation_event.potential_intent == mock_response_json["potential_intent"]

@patch('requests.post')
def test_call_llm_api_live_mode_api_failure(mock_post):
    """Test call_llm_api in live mode, API failure (mocking requests for isolation)."""
    mock_post.side_effect = HTTPError("Mock HTTP Error")

    raw_signals = [mock_screenshot_signal]
    with pytest.raises(RuntimeError, match="LLM API call failed"):
        llm_connector.call_llm_api(raw_signals, user_instruction="", use_mock=False)
    
    mock_post.assert_called_once()

@patch('requests.post')
def test_call_llm_api_live_mode_invalid_response(mock_post):
    """Test call_llm_api in live mode, invalid LLM response (schema validation, mocking requests)."""
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
        llm_connector.call_llm_api(raw_signals, user_instruction="", use_mock=False)
    
    mock_post.assert_called_once()


# --- Real Integration Tests with Mock Server ---

def test_call_llm_api_integration_default(mock_llm_server):
    """Test call_llm_api in live mode against the actual mock server (default response)."""
    raw_signals = [mock_screenshot_signal, mock_uia_signal] # Not Notepad
    observation_event = llm_connector.call_llm_api(raw_signals, user_instruction="", use_mock=False)

    assert isinstance(observation_event, ObservationEvent)
    assert observation_event.ui_state_summary == "Desktop is visible."
    assert observation_event.potential_intent == "Waiting for user instructions."

def test_call_llm_api_integration_dino_prompt(mock_llm_server):
    """Test call_llm_api in live mode against the actual mock server (Chrome Dino prompt)."""
    raw_signals = [mock_screenshot_signal, mock_uia_signal]
    user_instruction = "Please play chrome dino."
    observation_event = llm_connector.call_llm_api(raw_signals, user_instruction=user_instruction, use_mock=False)

    assert isinstance(observation_event, ObservationEvent)
    assert observation_event.ui_state_summary == "Google Chrome with Dino game is active."
    assert observation_event.potential_intent == "Play Chrome Dino Game."

def test_call_llm_api_integration_notepad_uia(mock_llm_server):
    """Test call_llm_api in live mode against the actual mock server (Notepad in UIA)."""
    raw_signals = [mock_screenshot_signal, mock_uia_notepad_signal]
    observation_event = llm_connector.call_llm_api(raw_signals, user_instruction="", use_mock=False)
    
    assert isinstance(observation_event, ObservationEvent)
    assert observation_event.ui_state_summary == "Notepad window is open and focused."
    assert observation_event.potential_intent == "User wants to type in Notepad."
