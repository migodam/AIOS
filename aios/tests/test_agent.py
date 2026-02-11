import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock

from aios.protocols.schema import ObservationEvent, RawSignal, UIATreeData, ActionPlan, LogData, ScreenshotData
from aios.memory.graph import GraphMemory
from aios.agent.main_agent import decide_action

@pytest.fixture
def mock_graph_memory(tmp_path):
    """Fixture for a mock GraphMemory instance."""
    graph_file = tmp_path / "mock_graph.json"
    return GraphMemory(graph_file)

def test_decide_action_notepad_typing_intent(mock_graph_memory):
    """
    Tests if the agent decides to TypeString when Notepad is observed
    and intent suggests typing.
    """
    # Mock an ObservationEvent indicating Notepad is open and user intent to type
    mock_observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[
            RawSignal(
                observer_id="mock_uia",
                artifact_path="/tmp/mock.json",
                artifact_hash="abc",
                data=UIATreeData(focused_window_title="Untitled - Notepad", tree_structure={"foo": "bar"})
            )
        ],
        ui_state_summary="User is viewing a new Notepad window.",
        environment_state_summary="System is running.",
        potential_intent="Preparing to type."
    )

    action_plan = decide_action(mock_observation, mock_graph_memory)

    assert isinstance(action_plan, ActionPlan)
    assert action_plan.action_type == "TypeString"
    assert "Hello from AIOS!" in action_plan.parameters["text"]
    assert action_plan.dry_run is True
    assert action_plan.origin_observation_id == mock_observation.observation_id

def test_decide_action_pilot_script_running(mock_graph_memory):
    """
    Tests if the agent decides to Log when pilot script is observed.
    """
    mock_observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Desktop is visible.",
        environment_state_summary="System is running the pilot script.",
        potential_intent="Monitoring system."
    )

    action_plan = decide_action(mock_observation, mock_graph_memory)

    assert isinstance(action_plan, ActionPlan)
    assert action_plan.action_type == "Log"
    assert "AIOS Agent observed pilot script running" in action_plan.parameters["message"]
    assert action_plan.dry_run is True
    assert action_plan.origin_observation_id == mock_observation.observation_id

def test_decide_action_no_specific_intent(mock_graph_memory):
    """
    Tests if the agent decides "NoAction" when no specific rules are met.
    """
    mock_observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[
            RawSignal(
                observer_id="mock_ss",
                artifact_path="/tmp/mock.png",
                artifact_hash="def",
                data=ScreenshotData(screen_size=(1920, 1080))
            )
        ],
        ui_state_summary="Generic desktop view.",
        environment_state_summary="System idle.",
        potential_intent="Browsing."
    )

    action_plan = decide_action(mock_observation, mock_graph_memory)

    assert isinstance(action_plan, ActionPlan)
    assert action_plan.action_type == "NoAction"
    assert action_plan.parameters == {}
    assert action_plan.dry_run is True
    assert action_plan.origin_observation_id == mock_observation.observation_id

def test_decide_action_graph_access(mock_graph_memory):
    """Tests that the agent can access graph memory properties."""
    # Ensure graph memory properties are accessible
    assert hasattr(mock_graph_memory, 'nodes')
    assert hasattr(mock_graph_memory, 'edges')
    # The agent's decide_action function should not modify the graph here,
    # but merely query it for orienting.
    
    mock_observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Test",
        environment_state_summary="Test",
        potential_intent="Test"
    )
    
    # We're just checking that the agent doesn't crash when accessing the graph
    action_plan = decide_action(mock_observation, mock_graph_memory)
    assert isinstance(action_plan, ActionPlan)

