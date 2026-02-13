from __future__ import annotations
import json
from typing import List, Any, Dict
from pydantic import ValidationError
from datetime import datetime
import uuid
import os

from aios.protocols.schema import RawSignal, ObservationEvent, AIOSBaseModel, UIATreeData, ScreenshotData, LogData
from aios.llm.llm_client import LLMClient

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

def _load_prompt_from_file(file_path: str) -> str:
    """Loads a prompt from a given file path."""
    # Construct the full path relative to the current script's directory
    # Assumes prompts directory is a sibling of protocols directory within aios
    base_dir = os.path.dirname(os.path.dirname(__file__)) # Go up to 'aios' directory
    full_path = os.path.join(base_dir, file_path)
    with open(full_path, 'r', encoding='utf-8') as f:
        return f.read()

def request_protocol_llm_observation(
    raw_signals: List[RawSignal], 
    llm_api_key: str, 
    protocol_llm_prompt_filename: str, # Changed to filename
    user_instruction: str = ""
) -> ObservationEvent:
    """
    Requests the Protocol LLM to parse raw signals into a structured ObservationEvent.

    Args:
        raw_signals: A list of RawSignal objects from various observers.
        llm_api_key: The API key for the LLM.
        protocol_llm_prompt_filename: Filename of the system prompt for the Protocol LLM.
        user_instruction: An optional instruction from the user, to be included in the prompt.

    Returns:
        An ObservationEvent object.
    """
    current_timestamp = datetime.utcnow()
    observation_id = str(uuid.uuid4())
    
    print(f"[{current_timestamp.isoformat()}] LLM Connector: Requesting Protocol LLM for observation...")

    llm_client = LLMClient(api_key=llm_api_key)
    
    # Load the system prompt
    system_prompt = _load_prompt_from_file(f"prompts/{protocol_llm_prompt_filename}")
    user_prompt = _construct_prompt_from_raw_signals(raw_signals)
    if user_instruction:
        user_prompt += f"\\n\\nUser Instruction: {user_instruction}" # Add user instruction to prompt
    
    from aios.protocols.schema import ProtocolLLMOutput # Import here to avoid circular dependency

    try:
        llm_output_dict = llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=ProtocolLLMOutput.model_json_schema() # Pass the schema for LLM to adhere to
        )
        
        protocol_llm_output = ProtocolLLMOutput.model_validate(llm_output_dict)

        llm_observation_event = ObservationEvent(
            observation_id=observation_id,
            raw_signals=raw_signals,
            ui_state_summary=protocol_llm_output.ui_state_summary,
            environment_state_summary="Not explicitly provided by ProtocolLLM", # ProtocolLLM doesn't explicitly output this.
            potential_intent=protocol_llm_output.intent
        )
        return llm_observation_event

    except ValidationError as e:
        print(f"LLM API response failed schema validation: {e}")
        raise RuntimeError(f"LLM response invalid: {e}")
    except Exception as e:
        print(f"LLM API call failed: {e}")
        raise RuntimeError(f"LLM API call failed: {e}")

from aios.protocols.schema import ActionPlan # Import here to avoid circular dependency

def request_core_agent_llm_action(
    observation_event: ObservationEvent,
    graph_memory_summary: str,
    user_instruction: str,
    llm_api_key: str,
    core_llm_prompt_filename: str
) -> ActionPlan:
    """
    Requests the Core Agent LLM to generate an ActionPlan.
    """
    print(f"LLM Connector: Requesting Core Agent LLM for action plan...")
    llm_client = LLMClient(api_key=llm_api_key)
    
    system_prompt = _load_prompt_from_file(f"prompts/{core_llm_prompt_filename}")
    
    # Construct user prompt for Core Agent LLM
    user_prompt = f"""
    Current Observation:
    {observation_event.model_dump_json(indent=2)}

    Graph Memory Summary:
    {graph_memory_summary}

    User Instruction:
    {user_instruction}

    Based on the above, provide a structured ActionPlan.
    """
    
    try:
        llm_output_dict = llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=ActionPlan.model_json_schema() # Pass the schema for LLM to adhere to
        )
        return ActionPlan.model_validate(llm_output_dict)
    except ValidationError as e:
        print(f"Core Agent LLM response failed schema validation: {e}")
        raise RuntimeError(f"Core Agent LLM response invalid: {e}")
    except Exception as e:
        print(f"Core Agent LLM call failed: {e}")
        raise RuntimeError(f"Core Agent LLM call failed: {e}")

