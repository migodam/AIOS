import pytest
from unittest.mock import MagicMock, patch
import uuid
from datetime import datetime
import json
from pathlib import Path

from aios.task_loop import TaskLoopController, CompletionJudge
from aios.protocols.schema import (
    TaskState,
    TaskResult,
    ObservationEvent,
    RawSignal,
    EventType,
    Event,
    ActionPlan,
    Receipt,
)
from aios.llm.llm_client import LLMClient

from aios.event_stream import JsonlLogger
from aios.memory.graph import GraphMemory

# --- Fixtures for TaskLoopController Tests ---

@pytest.fixture
def mock_llm_client():
    mock = MagicMock(spec=LLMClient)
    # Configure mock LLM to always return a simple ActionPlan for now
    mock.generate.return_value = {"action": {"action_type": "NoAction", "parameters": {}}, "expected_observation": "", "progress_update": {}, "done": False}
    return mock

@pytest.fixture
def mock_observer():
    mock = MagicMock()
    # Mock observe method to return a dummy ObservationEvent
    mock.observe.return_value = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Mock UI Summary - Notepad is not open.",
        environment_state_summary="Mock Environment Summary",
        potential_intent="Mock Intent"
    )
    return mock

@pytest.fixture
def mock_action_protocol():
    mock = MagicMock()
    # Mock verify_action_plan to return a successful VerifiedActionPlan
    mock.verify_action_plan.return_value = MagicMock(status="ready_for_execution", action_plan=ActionPlan(action_id=str(uuid.uuid4()), origin_observation_id=str(uuid.uuid4()), action_type="NoAction", parameters={}))
    return mock

@pytest.fixture
def mock_actuator():
    mock = MagicMock()
    # Mock execute_action to always return a successful Receipt
    mock.execute_action.return_value = Receipt(action_id=str(uuid.uuid4()), status="success", message="Action executed.")
    return mock

@pytest.fixture
def mock_event_stream():
    mock = MagicMock(spec=JsonlLogger)
    return mock

@pytest.fixture
def mock_graph_memory():
    mock = MagicMock(spec=GraphMemory)
    return mock

@pytest.fixture
def mock_completion_judge():
    mock = MagicMock(spec=CompletionJudge)
    # Default judge to not done
    mock.judge.return_value = {"updated_checklist": {}, "is_done": False, "missing_keys": ["all"]}
    return mock

@pytest.fixture
def task_loop_controller(
    mock_llm_client,
    mock_observer,
    mock_action_protocol,
    mock_actuator,
    mock_event_stream,
    mock_graph_memory,
    mock_completion_judge
):
    user_instruction = "Test Goal"
    max_steps = 3
    artifacts_dir = Path("mock_artifacts_dir") # Add mock artifacts_dir
    return TaskLoopController(
        user_instruction=user_instruction,
        max_steps=max_steps,
        artifacts_dir=artifacts_dir, # Pass artifacts_dir
        llm_client=mock_llm_client,
        observer=mock_observer,
        action_protocol=mock_action_protocol,
        actuator=mock_actuator,
        event_stream=mock_event_stream,
        graph_memory=mock_graph_memory,
        completion_judge=mock_completion_judge
    )

# --- CompletionJudge Tests ---

@pytest.fixture
def notepad_goal():
    return "Open Notepad, create new file, type Hello AIOS"

@pytest.fixture
def notepad_checklist_config():
    return {
        "notepad_opened": "UIA tree contains Notepad window.",
        "file_new": "Notepad title contains 'Untitled' or '无标题'.",
        "text_present": "UIA text content contains 'Hello AIOS'."
    }

def test_completion_judge_init(notepad_goal, notepad_checklist_config):
    judge = CompletionJudge(notepad_goal, notepad_checklist_config)
    assert judge.goal == notepad_goal
    assert judge.rule_based_checklist_config == notepad_checklist_config

def test_completion_judge_notepad_not_opened(notepad_goal, notepad_checklist_config):
    judge = CompletionJudge(notepad_goal, notepad_checklist_config)
    observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Some other window is focused.",
        environment_state_summary="",
        potential_intent=""
    )
    task_state = TaskState(goal=notepad_goal)
    results = judge.judge(task_state, observation)
    assert results["updated_checklist"]["notepad_opened"] is False
    assert results["is_done"] is False
    assert "notepad_opened" in results["missing_keys"]

def test_completion_judge_notepad_opened_english(notepad_goal, notepad_checklist_config):
    judge = CompletionJudge(notepad_goal, notepad_checklist_config)
    observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Focused Window: Untitled - Notepad",
        environment_state_summary="",
        potential_intent=""
    )
    task_state = TaskState(goal=notepad_goal)
    results = judge.judge(task_state, observation)
    assert results["updated_checklist"]["notepad_opened"] is True
    assert results["updated_checklist"]["file_new"] is True # 'Untitled' in title
    assert results["is_done"] is False # Text not present yet
    assert "text_present" in results["missing_keys"]

def test_completion_judge_notepad_opened_chinese(notepad_goal, notepad_checklist_config):
    judge = CompletionJudge(notepad_goal, notepad_checklist_config)
    observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Focused Window: 无标题 - 记事本",
        environment_state_summary="",
        potential_intent=""
    )
    task_state = TaskState(goal=notepad_goal)
    results = judge.judge(task_state, observation)
    assert results["updated_checklist"]["notepad_opened"] is True
    assert results["updated_checklist"]["file_new"] is True # '无标题' in title
    assert results["is_done"] is False # Text not present yet
    assert "text_present" in results["missing_keys"]

def test_completion_judge_notepad_all_done(notepad_goal, notepad_checklist_config):
    judge = CompletionJudge(notepad_goal, notepad_checklist_config)
    observation = ObservationEvent(
        observation_id=str(uuid.uuid4()),
        raw_signals=[],
        ui_state_summary="Focused Window: Untitled - Notepad (Hello AIOS present). Hello AIOS", # Added "Hello AIOS" to make text_present true
        environment_state_summary="",
        potential_intent=""
    )
    task_state = TaskState(goal=notepad_goal)
    task_state.checklist = {"notepad_opened": True, "file_new": True, "text_present": True} # Pre-fill for this test
    results = judge.judge(task_state, observation)
    assert results["updated_checklist"]["notepad_opened"] is True
    assert results["updated_checklist"]["file_new"] is True
    assert results["updated_checklist"]["text_present"] is True
    assert results["is_done"] is True
    assert not results["missing_keys"]

# --- TaskLoopController Tests ---

def test_task_loop_controller_init(task_loop_controller):
    assert task_loop_controller.max_steps == 3
    assert task_loop_controller.task_state.goal == "Test Goal"
    assert task_loop_controller.task_state.max_steps == 3

def test_task_loop_controller_loop_continues_and_max_steps_exceeded(task_loop_controller, mock_observer, mock_completion_judge, mock_event_stream, mock_graph_memory):
    mock_observer.observe.return_value = ObservationEvent(observation_id=str(uuid.uuid4()), raw_signals=[], ui_state_summary="UI", environment_state_summary="", potential_intent="")
    mock_completion_judge.judge.return_value = {"updated_checklist": {}, "is_done": False, "missing_keys": ["all"]} # Always not done

    result = task_loop_controller.run()
    assert result.status == "max_steps_exceeded"
    assert mock_observer.observe.call_count == 3 # Should observe max_steps times
    assert mock_event_stream.log_event.call_count > 0 # At least initial state and final state

def test_task_loop_controller_loop_stops_when_complete(task_loop_controller, mock_observer, mock_completion_judge, mock_event_stream, mock_graph_memory):
    # Mock judge to complete on second step
    completion_results_first_step = {"updated_checklist": {"notepad_opened": False}, "is_done": False, "missing_keys": ["notepad_opened"]}
    completion_results_second_step = {"updated_checklist": {"notepad_opened": True, "file_new": True, "text_present": True}, "is_done": True, "missing_keys": []}
    
    mock_completion_judge.judge.side_effect = [
        completion_results_first_step,
        completion_results_second_step
    ]
    mock_observer.observe.return_value = ObservationEvent(observation_id=str(uuid.uuid4()), raw_signals=[], ui_state_summary="UI", environment_state_summary="", potential_intent="")

    result = task_loop_controller.run()
    assert result.status == "success"
    assert "completed successfully" in result.final_summary
    assert mock_observer.observe.call_count == 2 # Stops after 2 observations

def test_task_loop_controller_loop_exits_on_critical_failure(task_loop_controller, mock_actuator, mock_observer, mock_event_stream, mock_graph_memory):
    mock_actuator.execute_action.side_effect = Exception("Critical Actuator Failure!")
    mock_observer.observe.return_value = ObservationEvent(observation_id=str(uuid.uuid4()), raw_signals=[], ui_state_summary="UI", environment_state_summary="", potential_intent="")

    result = task_loop_controller.run()
    assert result.status == "failed"
    assert "Critical Actuator Failure!" in result.final_summary
    assert mock_observer.observe.call_count == 1 # Fails on first action attempt

def test_task_loop_controller_stuck_loop_detection(task_loop_controller, mock_observer, mock_action_protocol, mock_actuator, mock_completion_judge, mock_event_stream, mock_graph_memory):
    task_loop_controller.max_steps = 10 # Set enough steps to trigger stuck detection
    task_loop_controller.task_state.stuck_threshold = 3 # Easier to test

    # Simulate repeated action and no progress from judge
    mock_action_protocol.verify_action_plan.return_value = MagicMock(status="ready_for_execution", action_plan=ActionPlan(action_id=str(uuid.uuid4()), origin_observation_id=str(uuid.uuid4()), action_type="KeyPress", parameters={"key": "space"}))
    mock_actuator.execute_action.return_value = Receipt(action_id=str(uuid.uuid4()), status="success", message="Action executed.")
    mock_observer.observe.return_value = ObservationEvent(observation_id=str(uuid.uuid4()), raw_signals=[], ui_state_summary="UI", environment_state_summary="", potential_intent="")
    mock_completion_judge.judge.return_value = {"updated_checklist": {}, "is_done": False, "missing_keys": ["all"]}

    result = task_loop_controller.run()
    assert result.status == "stuck_loop_detected"
    assert "repeated actions" in result.final_summary
    # Should run stuck_threshold times (first action + stuck_threshold-1 repeats)
    assert mock_observer.observe.call_count == task_loop_controller.task_state.stuck_threshold
    assert mock_actuator.execute_action.call_count == task_loop_controller.task_state.stuck_threshold
    assert mock_event_stream.log_event.call_count > task_loop_controller.task_state.stuck_threshold * 2 # Observation + TaskState + Action + Receipt events per step