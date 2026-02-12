import pytest
from pathlib import Path
import json
from datetime import datetime
import uuid

from aios.memory.graph import GraphMemory
from aios.protocols.schema import ObservationEvent, RawSignal, ScreenshotData, UIATreeData, GraphUpdate, LLMResponseMock

# --- Fixtures for reusable test data ---
@pytest.fixture
def temp_graph_file(tmp_path):
    """Provides a temporary file path for graph memory."""
    return tmp_path / "graph_memory.json"

@pytest.fixture
def mock_observation_event_initial():
    """Returns an initial mock ObservationEvent."""
    return ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[RawSignal(observer_id="test", artifact_path="path", artifact_hash="hash", data=ScreenshotData(screen_size=(1,1)))],
        ui_state_summary="Desktop is visible.",
        environment_state_summary="System idle.",
        potential_intent="Waiting for instructions."
    )

@pytest.fixture
def mock_observation_event_changed_intent():
    """Returns a mock ObservationEvent with changed intent."""
    return ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[RawSignal(observer_id="test", artifact_path="path", artifact_hash="hash", data=ScreenshotData(screen_size=(1,1)))],
        ui_state_summary="Desktop is visible.",
        environment_state_summary="System idle.",
        potential_intent="Play Chrome Dino Game."
    )

@pytest.fixture
def mock_observation_event_changed_ui():
    """Returns a mock ObservationEvent with changed UI summary."""
    return ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[RawSignal(observer_id="test", artifact_path="path", artifact_hash="hash", data=UIATreeData(focused_window_title="Dino Game", tree_structure={}))],
        ui_state_summary="Chrome Dino game running.",
        environment_state_summary="System idle.",
        potential_intent="Waiting for instructions."
    )

@pytest.fixture
def mock_observation_event_no_change():
    """Returns a mock ObservationEvent that is identical to the initial one."""
    return ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[RawSignal(observer_id="test", artifact_path="path", artifact_hash="hash", data=ScreenshotData(screen_size=(1,1)))],
        ui_state_summary="Desktop is visible.",
        environment_state_summary="System idle.",
        potential_intent="Waiting for instructions."
    )

# --- Tests for GraphMemory ---

def test_graph_memory_init(temp_graph_file):
    """Test GraphMemory initialization and empty state."""
    graph = GraphMemory(temp_graph_file)
    assert graph.file_path == temp_graph_file
    assert not graph.graph_updates
    assert graph._previous_observation is None

def test_graph_memory_save_load(temp_graph_file, mock_observation_event_initial):
    """Test saving and loading graph memory."""
    graph = GraphMemory(temp_graph_file)
    graph.update(mock_observation_event_initial)
    graph.save()

    loaded_graph = GraphMemory(temp_graph_file)
    assert len(loaded_graph.graph_updates) == 1
    assert loaded_graph._previous_observation == mock_observation_event_initial
    assert loaded_graph.graph_updates[0].observation_id == mock_observation_event_initial.observation_id
    assert "Initial observation" in loaded_graph.graph_updates[0].summary_of_change

def test_graph_memory_update_initial(temp_graph_file, mock_observation_event_initial):
    """Test update with the initial observation."""
    graph = GraphMemory(temp_graph_file)
    graph_update = graph.update(mock_observation_event_initial)

    assert graph_update is not None
    assert len(graph.graph_updates) == 1
    assert graph._previous_observation == mock_observation_event_initial
    assert graph.graph_updates[0].observation_id == mock_observation_event_initial.observation_id
    assert "Initial observation" in graph.graph_updates[0].summary_of_change

def test_graph_memory_update_changed_intent(temp_graph_file, mock_observation_event_initial, mock_observation_event_changed_intent):
    """Test update when intent changes."""
    graph = GraphMemory(temp_graph_file)
    graph.update(mock_observation_event_initial) # First update

    # Second update with changed intent
    graph_update = graph.update(mock_observation_event_changed_intent)

    assert graph_update is not None
    assert len(graph.graph_updates) == 2
    assert graph._previous_observation == mock_observation_event_changed_intent
    assert "Intent changed" in graph_update.summary_of_change
    assert "Play Chrome Dino Game." in graph_update.summary_of_change

def test_graph_memory_update_changed_ui(temp_graph_file, mock_observation_event_initial, mock_observation_event_changed_ui):
    """Test update when UI summary changes."""
    graph = GraphMemory(temp_graph_file)
    graph.update(mock_observation_event_initial) # First update

    # Second update with changed UI
    graph_update = graph.update(mock_observation_event_changed_ui)

    assert graph_update is not None
    assert len(graph.graph_updates) == 2
    assert graph._previous_observation == mock_observation_event_changed_ui
    assert "UI summary changed" in graph_update.summary_of_change
    assert "Chrome Dino game running." in graph_update.summary_of_change

def test_graph_memory_update_no_change(temp_graph_file, mock_observation_event_initial, mock_observation_event_no_change):
    """Test update when no significant change occurs."""
    graph = GraphMemory(temp_graph_file)
    graph.update(mock_observation_event_initial) # First update

    # Second update with no change
    graph_update = graph.update(mock_observation_event_no_change)

    assert graph_update is None
    assert len(graph.graph_updates) == 1 # Only the initial update should be present
    assert graph._previous_observation == mock_observation_event_no_change

def test_graph_memory_query_all(temp_graph_file, mock_observation_event_initial, mock_observation_event_changed_intent):
    """Test querying all graph updates."""
    graph = GraphMemory(temp_graph_file)
    graph.update(mock_observation_event_initial)
    graph.update(mock_observation_event_changed_intent)

    results = graph.query(limit=10)
    assert len(results) == 2
    assert "Intent changed" in results[0].summary_of_change # Most recent first
    assert "Initial observation" in results[1].summary_of_change

def test_graph_memory_query_filter_by_intent(temp_graph_file, mock_observation_event_initial, mock_observation_event_changed_intent, mock_observation_event_changed_ui):
    """Test querying graph updates filtered by intent."""
    graph = GraphMemory(temp_graph_file)
    graph.update(mock_observation_event_initial) # Initial: Waiting for instructions
    graph.update(mock_observation_event_changed_intent) # Changed: Play Chrome Dino Game
    graph.update(mock_observation_event_changed_ui) # Changed: Waiting for instructions

    results_dino = graph.query(search_intent="Dino", limit=10)
    assert len(results_dino) == 2
    assert "Play Chrome Dino Game." in results_dino[0].summary_of_change

    results_waiting = graph.query(search_intent="Waiting", limit=10)
    assert len(results_waiting) == 3
    assert "Waiting for instructions" in results_waiting[0].summary_of_change # Changed UI, but original intent
    assert "Initial observation" in results_waiting[2].summary_of_change

def test_graph_memory_query_limit(temp_graph_file, mock_observation_event_initial, mock_observation_event_changed_intent, mock_observation_event_changed_ui):
    """Test query limit functionality."""
    graph = GraphMemory(temp_graph_file)
    graph.update(mock_observation_event_initial)
    graph.update(mock_observation_event_changed_intent)
    graph.update(mock_observation_event_changed_ui)

    results = graph.query(limit=2)
    assert len(results) == 2
    assert "UI summary changed" in results[0].summary_of_change # Most recent
    assert "Intent changed" in results[1].summary_of_change

# Test for GraphUpdate schema validation (implicitly covered by GraphMemory usage)
def test_graph_update_schema_validation():
    """Test direct GraphUpdate schema validation."""
    gu = GraphUpdate(
        observation_id=str(uuid.uuid4()),
        summary_of_change="Test change",
        metadata={"key": "value"}
    )
    assert isinstance(gu.timestamp, datetime)
    assert gu.summary_of_change == "Test change"
    assert gu.metadata["key"] == "value"
