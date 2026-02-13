import pytest
from unittest.mock import patch, MagicMock
import json
import uuid # Import uuid for ActionPlan test
from aios.llm.llm_client import LLMClient
from aios.protocols.schema import ProtocolLLMOutput, ActionPlan

# Mock API Key for testing
TEST_API_KEY = "test-api-key"

@pytest.fixture
def mock_genai_model():
    """Mocks google.generativeai.GenerativeModel and its generate_content method."""
    with patch('google.generativeai.GenerativeModel') as MockGenerativeModel:
        mock_instance = MockGenerativeModel.return_value
        # Mock the structure of the response object
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()

        mock_response.candidates = [mock_candidate]
        mock_candidate.content.parts = [mock_part]
        mock_part.text = "" # Default empty text

        mock_instance.generate_content.return_value = mock_response
        yield mock_instance

def test_llm_client_initialization():
    """Test that LLMClient initializes correctly."""
    with patch('google.generativeai.configure') as mock_configure:
        client = LLMClient(api_key=TEST_API_KEY)
        mock_configure.assert_called_once_with(api_key=TEST_API_KEY)
        assert client.model_name == "gemini-pro"
        assert client.temperature == 0.7

def test_llm_client_generate_text_only(mock_genai_model):
    """Test generate method for text-only output."""
    mock_genai_model.generate_content.return_value.candidates[0].content.parts[0].text = "Hello, world!"
    client = LLMClient(api_key=TEST_API_KEY)
    response = client.generate(system_prompt="system", user_prompt="user")
    
    assert response == {"text": "Hello, world!"}
    mock_genai_model.generate_content.assert_called_once()
    args, kwargs = mock_genai_model.generate_content.call_args
    assert kwargs['generation_config']['temperature'] == 0.7
    assert 'response_mime_type' not in kwargs['generation_config']

def test_llm_client_generate_json_output_protocol_llm(mock_genai_model):
    """Test generate method for JSON output with ProtocolLLMOutput schema."""
    mock_json_output = {
        "intent": "Play Chrome Dino",
        "ui_state_summary": "Chrome window with Dino game active",
        "confidence": 0.85
    }
    mock_genai_model.generate_content.return_value.candidates[0].content.parts[0].text = json.dumps(mock_json_output)
    
    client = LLMClient(api_key=TEST_API_KEY)
    response = client.generate(
        system_prompt="system", 
        user_prompt="user", 
        json_schema=ProtocolLLMOutput.model_json_schema()
    )
    
    assert response == mock_json_output
    args, kwargs = mock_genai_model.generate_content.call_args
    assert kwargs['generation_config']['response_mime_type'] == "application/json"

def test_llm_client_generate_json_output_action_plan(mock_genai_model):
    """Test generate method for JSON output with ActionPlan schema."""
    mock_json_output = {
        "action_id": str(uuid.uuid4()),
        "origin_observation_id": str(uuid.uuid4()),
        "action_type": "KeyPress",
        "parameters": {"key": "space"},
        "constraints": {},
        "dry_run": False
    }
    mock_genai_model.generate_content.return_value.candidates[0].content.parts[0].text = json.dumps(mock_json_output)
    
    client = LLMClient(api_key=TEST_API_KEY)
    response = client.generate(
        system_prompt="system", 
        user_prompt="user", 
        json_schema=ActionPlan.model_json_schema()
    )
    
    assert response == mock_json_output
    args, kwargs = mock_genai_model.generate_content.call_args
    assert kwargs['generation_config']['response_mime_type'] == "application/json"

def test_llm_client_generate_invalid_json_raises_error(mock_genai_model):
    """Test that generate method raises ValueError for invalid JSON output when schema is provided."""
    mock_genai_model.generate_content.return_value.candidates[0].content.parts[0].text = "this is not json"
    client = LLMClient(api_key=TEST_API_KEY)
    with pytest.raises(ValueError, match="LLM did not return valid JSON"):
        client.generate(system_prompt="system", user_prompt="user", json_schema={"type": "object"})

@patch('time.sleep', return_value=None) # Mock time.sleep to speed up tests
def test_llm_client_retry_mechanism(mock_sleep, mock_genai_model):
    """Test that the retry mechanism works."""
    # Simulate a transient error followed by a success
    mock_genai_model.generate_content.side_effect = [
        Exception("Transient error 1"),
        Exception("Transient error 2"),
        mock_genai_model.generate_content.return_value # Success on third attempt
    ]
    mock_genai_model.generate_content.return_value.candidates[0].content.parts[0].text = "Success!"

    client = LLMClient(api_key=TEST_API_KEY)
    response = client.generate(system_prompt="system", user_prompt="user")

    assert response == {"text": "Success!"}
    assert mock_genai_model.generate_content.call_count == 3

def test_llm_client_no_candidates_raises_error(mock_genai_model):
    """Test that ValueError is raised if LLM response has no candidates."""
    mock_genai_model.generate_content.return_value.candidates = []
    client = LLMClient(api_key=TEST_API_KEY)
    with pytest.raises(ValueError, match="LLM response contained no candidates."):
        client.generate(system_prompt="system", user_prompt="user")

def test_llm_client_no_content_parts_raises_error(mock_genai_model):
    """Test that ValueError is raised if LLM response has no content parts."""
    mock_genai_model.generate_content.return_value.candidates[0].content.parts = []
    client = LLMClient(api_key=TEST_API_KEY)
    with pytest.raises(ValueError, match="LLM response contained no content parts."):
        client.generate(system_prompt="system", user_prompt="user")