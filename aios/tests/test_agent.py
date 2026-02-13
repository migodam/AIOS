import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock

from aios.protocols.schema import ObservationEvent, RawSignal, UIATreeData, ActionPlan, LogData, ScreenshotData
from aios.memory.graph import GraphMemory
from aios.agent.main_agent import decide_action
from aios.protocols.llm_connector import request_core_agent_llm_action # Import the function to mock

@pytest.fixture
def mock_graph_memory(tmp_path):
    \"\"\"Fixture for a mock GraphMemory instance.\"\"\"
    graph_file = tmp_path / "mock_graph.json"
    return GraphMemory(graph_file)

@pytest.fixture
def mock_observation_event():
    return ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Mock UI state",
        environment_state_summary="Mock env state",
        potential_intent="Mock intent"
    )

@patch('aios.protocols.llm_connector.request_core_agent_llm_action')
def test_decide_action_calls_llm_connector(mock_llm_connector_call, mock_observation_event, mock_graph_memory):
    \"\"\"
    Test that decide_action calls request_core_agent_llm_action with correct arguments
    and returns its result.
    \"\"\"
    mock_action_plan = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=mock_observation_event.observation_id,
        action_type="TypeString",
        parameters={"text": "Hello AIOS!"},
        constraints={},
        dry_run=False
    )
    mock_llm_connector_call.return_value = mock_action_plan

    user_instruction = "Open Notepad and type Hello AIOS"
    llm_api_key = "test_key"
    core_llm_prompt_filename = "core_llm_prompt.txt"

    action_plan = decide_action(
        observation_event=mock_observation_event,
        graph_memory=mock_graph_memory,
        user_instruction=user_instruction,
        llm_api_key=llm_api_key,
        core_llm_prompt_filename=core_llm_prompt_filename
    )

    mock_llm_connector_call.assert_called_once_with(
        observation_event=mock_observation_event,
        graph_memory_summary=f"Graph contains {len(mock_graph_memory.nodes)} nodes and {len(mock_graph_memory.edges)} edges. "
                             f"Most recent observation intent: {mock_observation_event.potential_intent}. "
                             f"Most recent UI summary: {mock_observation_event.ui_state_summary}.",
        user_instruction=user_instruction,
        llm_api_key=llm_api_key,
        core_llm_prompt_filename=core_llm_prompt_filename
    )
    assert action_plan == mock_action_plan
    assert isinstance(action_plan, ActionPlan)

def test_decide_action_graph_summary_includes_current_observation(mock_llm_connector_call, mock_observation_event, mock_graph_memory):
    \"\"\"
    Test that the graph memory summary passed to the LLM includes details from the current observation.
    \"\"\"
    mock_llm_connector_call.return_value = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=mock_observation_event.observation_id,
        action_type="NoAction", parameters={}, constraints={}, dry_run=False
    )
    
    decide_action(
        observation_event=mock_observation_event,
        graph_memory=mock_graph_memory,
        user_instruction="some instruction",
        llm_api_key="key",
        core_llm_prompt_filename="core.txt"
    )

    # Check the graph_memory_summary argument
    _, kwargs = mock_llm_connector_call.call_args
    summary = kwargs['graph_memory_summary']
    assert f"Most recent observation intent: {mock_observation_event.potential_intent}" in summary
    assert f"Most recent UI summary: {mock_observation_event.ui_state_summary}" in summary

def test_decide_action_returns_llm_action_plan_on_no_action(mock_llm_connector_call, mock_observation_event, mock_graph_memory):
    \"\"\"
    Test that decide_action correctly returns an ActionPlan even if the LLM decides 'NoAction'.
    \"\"\"
    mock_action_plan_no_action = ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=mock_observation_event.observation_id,
        action_type="NoAction",
        parameters={},
        constraints={},
        dry_run=False
    )
    mock_llm_connector_call.return_value = mock_action_plan_no_action

    action_plan = decide_action(
        observation_event=mock_observation_event,
        graph_memory=mock_graph_memory,
        user_instruction="Just observe",
        llm_api_key="test_key",
        core_llm_prompt_filename="core_llm_prompt.txt"
    )

    assert action_plan == mock_action_plan_no_action
    assert action_plan.action_type == "NoAction"
