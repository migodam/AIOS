import pytest
from pydantic import ValidationError
import uuid
from datetime import datetime

from aios.protocols.schema import (
    AIOSBaseModel,
    ScreenshotData,
    UIATreeData,
    RawSignal,
    ObservationEvent,
    ActionPlan,
    Receipt,
    EventType,
    Event
)

def test_raw_signal_screenshot_serialization():
    """Tests creating and serializing a screenshot RawSignal."""
    data = ScreenshotData(screen_size=(1920, 1080))
    signal = RawSignal(
        observer_id="ss_obs_1",
        artifact_path="/tmp/ss.png",
        artifact_hash="abcde12345",
        data=data
    )
    
    json_str = signal.model_dump_json()
    reloaded_signal = RawSignal.model_validate_json(json_str)
    
    assert reloaded_signal.observer_id == "ss_obs_1"
    assert reloaded_signal.data.screen_size == (1920, 1080)
    assert isinstance(reloaded_signal.timestamp, datetime)

def test_observation_event_serialization():
    """Tests creating and serializing an ObservationEvent."""
    obs_id = str(uuid.uuid4())
    event = ObservationEvent(
        observation_id=obs_id,
        raw_signals=[],
        ui_state_summary="User is looking at the home screen.",
        environment_state_summary="System idle.",
        potential_intent="Waiting for user input."
    )
    
    json_str = event.model_dump_json()
    reloaded_event = ObservationEvent.model_validate_json(json_str)

    assert reloaded_event.observation_id == obs_id
    assert reloaded_event.potential_intent == "Waiting for user input."

def test_action_plan_serialization():
    """Tests creating and serializing an ActionPlan."""
    action_id = str(uuid.uuid4())
    obs_id = str(uuid.uuid4())
    plan = ActionPlan(
        action_id=action_id,
        origin_observation_id=obs_id,
        action_type="KeyPress",
        parameters={"key": "space"},
        dry_run=False
    )

    json_str = plan.model_dump_json()
    reloaded_plan = ActionPlan.model_validate_json(json_str)

    assert reloaded_plan.action_id == action_id
    assert reloaded_plan.parameters["key"] == "space"
    assert reloaded_plan.dry_run is False

def test_receipt_serialization():
    """Tests creating and serializing a Receipt."""
    action_id = str(uuid.uuid4())
    receipt = Receipt(
        action_id=action_id,
        status="success",
        message="Action completed.",
        latency_ms=123.45
    )
    
    json_str = receipt.model_dump_json()
    reloaded_receipt = Receipt.model_validate_json(json_str)

    assert reloaded_receipt.action_id == action_id
    assert reloaded_receipt.status == "success"

def test_generic_event_wrapper_serialization():
    """Tests that the generic Event model can wrap other models."""
    action_id = str(uuid.uuid4())
    receipt = Receipt(
        action_id=action_id,
        status="success",
        message="Action completed.",
        latency_ms=123.45
    )
    
    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=EventType.RECEIPT,
        payload=receipt
    )

    json_str = event.model_dump_json()
    reloaded_event = Event.model_validate_json(json_str)

    assert reloaded_event.event_type == EventType.RECEIPT
    assert isinstance(reloaded_event.payload, Receipt)
    assert reloaded_event.payload.action_id == action_id

def test_receipt_invalid_status_raises_error():
    """Tests that an invalid 'status' literal for Receipt raises a ValidationError."""
    with pytest.raises(ValidationError, match="Input should be 'success', 'failure', 'rejected_unsafe' or 'dry_run_success'"):
        Receipt(action_id="123", status="pending", message="test", latency_ms=0.0)

def test_screenshotdata_invalid_type_raises_error():
    """Tests that providing a list instead of a tuple in strict mode raises a ValidationError."""
    with pytest.raises(ValidationError, match="Input should be a valid tuple"):
        # In strict mode, a list should not be coerced into a tuple.
        # We must use model_validate for this, as the constructor itself is lax.
        ScreenshotData.model_validate({'screen_size': [1920, 1080]}, strict=True)

def test_observation_missing_fields_raises_error():
    """Tests that missing required fields for ObservationEvent raises a ValidationError."""
    with pytest.raises(ValidationError, match="Field required"):
        ObservationEvent(observation_id="123", raw_signals=[])
