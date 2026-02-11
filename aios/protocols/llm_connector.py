from __future__ import annotations
import json
from typing import List, Any, Dict
import requests
from pydantic import ValidationError

from aios.protocols.schema import RawSignal, ObservationEvent, AIOSBaseModel, UIATreeData, ScreenshotData, LogData
import uuid
from datetime import datetime

# Define a placeholder LLM API endpoint. This will not exist, so mock mode is crucial.
LLM_API_ENDPOINT = "http://localhost:8080/v1/chat/completions" # Based on simulated answer to Q2

class LLMResponseMock(AIOSBaseModel):
    """
    Mock structure for an LLM response that would contain structured
    observation data. This helps in validating the mock output.
    """
    ui_state_summary: str
    environment_state_summary: str
    potential_intent: str

def _search_uia_tree_for_process(tree: Dict[str, Any], class_name_to_find: str) -> bool:
    """
    Helper function to recursively search a UIA tree structure for a node with a specific class name.
    """
    if tree is None:
        return False
    
    current_class_name = tree.get("class_name")
    # print(f"DEBUG: Searching for '{class_name_to_find}', current node class_name: '{current_class_name}'") # DEBUG
    # Check current node's class name
    if current_class_name == class_name_to_find:
        # print(f"DEBUG: Found '{class_name_to_find}'!") # DEBUG
        return True
    
    # Check children
    for child in tree.get("children", []):
        if _search_uia_tree_for_process(child, class_name_to_find):
            return True
            
    return False

def _construct_prompt_from_raw_signals(raw_signals: List[RawSignal]) -> str:
    """
    Constructs a textual prompt for the LLM based on raw signals.
    """
    prompt_parts = ["Analyze the following raw observations and summarize the UI state, environment state, and potential user intent:\n"]

    for signal in raw_signals:
        prompt_parts.append(f"\n--- Raw Signal: {signal.observer_id} (Type: {signal.data.__class__.__name__}) ---")
        if isinstance(signal.data, ScreenshotData):
            prompt_parts.append(f"Screenshot taken at {signal.timestamp} (File: {signal.artifact_path}). Screen size: {signal.data.screen_size[0]}x{signal.data.screen_size[1]}.")
            # In a real scenario, we might describe the image or attach it.
        elif isinstance(signal.data, UIATreeData):
            prompt_parts.append(f"UIA Tree for '{signal.data.focused_window_title}' captured at {signal.timestamp} (File: {signal.artifact_path}).")
            prompt_parts.append(f"Key elements: {json.dumps(signal.data.tree_structure.get('children', [])[:3], indent=2)}") # First 3 children for brevity
        elif isinstance(signal.data, LogData):
            prompt_parts.append(f"Log data from {signal.data.log_source} captured at {signal.timestamp}.")
            prompt_parts.append(f"Recent log lines: {' '.join(signal.data.new_lines[:5])}...") # First 5 lines for brevity
        else:
            prompt_parts.append(f"Unknown raw signal data type: {type(signal.data)}.")
        prompt_parts.append(f"Artifact Hash: {signal.artifact_hash}")
        
    return "\n".join(prompt_parts)

def call_llm_api(raw_signals: List[RawSignal], use_mock: bool = True) -> ObservationEvent:
    """
    Calls an external LLM API to parse raw signals into a structured ObservationEvent.
    If use_mock is True, a predefined mock response is returned.

    Args:
        raw_signals: A list of RawSignal objects from various observers.
        use_mock: If True, returns a mock LLM response instead of making an API call.

    Returns:
        An ObservationEvent object.
    """
    print("DEBUG: Entered call_llm_api function.") # Added debug print
    current_timestamp = datetime.utcnow()
    observation_id = str(uuid.uuid4())

    if use_mock:
        print(f"[{current_timestamp.isoformat()}] LLM Connector: Using mock LLM response.")
        
        # Simulate a simple summary based on presence of signals
        ui_summary = "UI at desktop."
        env_summary = "System appears normal."
        intent = "Waiting for user input."
        
        notepad_present = False
        for signal in raw_signals:
            if isinstance(signal.data, ScreenshotData):
                ui_summary = f"Desktop screenshot (size {signal.data.screen_size[0]}x{signal.data.screen_size[1]}) captured."
            elif isinstance(signal.data, UIATreeData):
                ui_summary += f" Focused window: {signal.data.focused_window_title}."
                # Use the helper function to search for Notepad
                if _search_uia_tree_for_process(signal.data.tree_structure, "Notepad"):
                    notepad_present = True
            elif isinstance(signal.data, LogData):
                env_summary = f"Recent logs show activity in {signal.data.log_source}."
        
        # print(f"DEBUG: notepad_present = {notepad_present}") # DEBUG
        if notepad_present:
            intent = "Preparing to type."
        # print(f"DEBUG: Final intent = '{intent}'") # DEBUG
        
        mock_response_data = LLMResponseMock(
            ui_state_summary=ui_summary,
            environment_state_summary=env_summary,
            potential_intent=intent
        )
        
        # Construct ObservationEvent from mock data
        mock_observation_event = ObservationEvent(
            observation_id=observation_id,
            raw_signals=raw_signals,
            ui_state_summary=mock_response_data.ui_state_summary,
            environment_state_summary=mock_response_data.environment_state_summary,
            potential_intent=mock_response_data.potential_intent
        )
        return mock_observation_event
    else:
        print(f"[{current_timestamp.isoformat()}] LLM Connector: Calling external LLM API at {LLM_API_ENDPOINT}...")
        prompt = _construct_prompt_from_raw_signals(raw_signals)
        
        payload = {
            "model": "gpt-4o", # Placeholder for an actual LLM model
            "messages": [
                {"role": "system", "content": "You are an AIOS Protocol1 parser. Extract UI state, environment state, and user intent from raw observations."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"} # Assuming JSON output
        }
        
        try:
            response = requests.post(
                LLM_API_ENDPOINT,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30 # 30 seconds timeout
            )
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            
            llm_output = response.json()
            
            # Assuming LLM output adheres to LLMResponseMock structure
            llm_response_data = LLMResponseMock.model_validate(llm_output)

            # Construct ObservationEvent from LLM data
            llm_observation_event = ObservationEvent(
                observation_id=observation_id,
                raw_signals=raw_signals,
                ui_state_summary=llm_response_data.ui_state_summary,
                environment_state_summary=llm_response_data.environment_state_summary,
                potential_intent=llm_response_data.potential_intent
            )
            return llm_observation_event

        except requests.exceptions.RequestException as e:
            print(f"LLM API call failed due to network/request error: {e}")
            # Fallback to a basic rule-based parsing or raise, depending on design
            raise RuntimeError(f"LLM API call failed: {e}")
        except ValidationError as e:
            print(f"LLM API response failed schema validation: {e}")
            raise RuntimeError(f"LLM response invalid: {e}")
        except json.JSONDecodeError as e:
            print(f"LLM API response was not valid JSON: {e}")
            raise RuntimeError(f"LLM response not JSON: {e}")

