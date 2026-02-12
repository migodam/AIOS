from __future__ import annotations
import time
from typing import Any, Dict
from datetime import datetime

# Import pynput for keyboard control
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController # ADDED

from aios.protocols.schema import Receipt, EventType, Event, ActionPlan, KeyPressParameters, MouseClickParameters, TypeStringParameters # ADDED new parameter schemas
from aios.protocols.action_protocol import VerifiedActionPlan

def execute_action(verified_action_plan: VerifiedActionPlan) -> Receipt:
    """
    Executes the action specified in the VerifiedActionPlan.

    Args:
        verified_action_plan: A VerifiedActionPlan object from Protocol2.

    Returns:
        A Receipt object detailing the outcome of the execution.
    """
    start_time = time.perf_counter()
    action = verified_action_plan.action_plan
    
    receipt_status = "failure"
    receipt_message = "Action could not be executed due to unknown error."

    try:
        if verified_action_plan.status == "rejected_unsafe":
            receipt_status = "rejected_unsafe"
            receipt_message = "Action was rejected by Protocol2 as unsafe."
            print(f"Actuator: {receipt_message}")
            return Receipt(
                action_id=action.action_id,
                status=receipt_status,
                message=receipt_message,
                latency_ms=(time.perf_counter() - start_time) * 1000
            )
        
        if verified_action_plan.status == "dry_run_completed":
            receipt_status = "dry_run_success"
            receipt_message = f"Action completed successfully in dry-run mode. Preview: {verified_action_plan.actuator_preview}"
            print(f"Actuator: {receipt_message}")
            return Receipt(
                action_id=action.action_id,
                status=receipt_status,
                message=receipt_message,
                latency_ms=(time.perf_counter() - start_time) * 1000
            )

        if verified_action_plan.status == "ready_for_execution":
            print(f"Actuator: Executing action '{action.action_type}' (ID: {action.action_id})...")
            keyboard = KeyboardController()
            mouse = MouseController() # ADDED
            
            if action.action_type == "TypeString":
                # Validate parameters against the schema
                params = TypeStringParameters.model_validate(action.parameters) # ADDED VALIDATION
                text_to_type = params.text # Access via validated model
                if text_to_type:
                    keyboard.type(str(text_to_type))
                    receipt_status = "success"
                    receipt_message = f"Successfully typed: '{text_to_type}'"
                else:
                    receipt_status = "failure"
                    receipt_message = "TypeString action missing 'text' parameter."
            
            elif action.action_type == "KeyPress": # ADDED KEYPRESS LOGIC
                # Validate parameters against the schema
                params = KeyPressParameters.model_validate(action.parameters)
                key_to_press = params.key
                modifiers = params.modifiers

                # pynput expects keys like 'Key.space', 'Key.enter', or 'c'
                # Handle special keys
                if key_to_press in ["space", "enter", "esc", "tab", "up", "down", "left", "right", "f5"]:
                    # Using eval to get the actual Key object from pynput
                    # This is generally unsafe, but for specific known keys and internal usage, it's acceptable.
                    # A safer approach for production would be a direct mapping dictionary.
                    try:
                        from pynput.keyboard import Key
                        actual_key = getattr(Key, key_to_press, key_to_press) # Fallback to string if not special Key
                    except AttributeError:
                        actual_key = key_to_press # Treat as character if not found in Key enum

                    # Apply modifiers
                    for mod in modifiers:
                        try:
                            actual_mod = getattr(Key, mod)
                            keyboard.press(actual_mod)
                        except AttributeError:
                            # Log warning for unknown modifier
                            print(f"WARNING: Unknown modifier '{mod}' for KeyPress action.")
                    
                    keyboard.press(actual_key)
                    keyboard.release(actual_key)

                    for mod in modifiers:
                        try:
                            actual_mod = getattr(Key, mod)
                            keyboard.release(actual_mod)
                        except AttributeError:
                            pass # Already warned

                    receipt_status = "success"
                    receipt_message = f"Successfully pressed key: '{key_to_press}' with modifiers {modifiers}"
                else:
                    # Assume it's a character key
                    keyboard.type(str(key_to_press)) # type() automatically handles press/release
                    receipt_status = "success"
                    receipt_message = f"Successfully typed character key: '{key_to_press}'"
            
            elif action.action_type == "MouseClick": # ADDED MOUSECLICK LOGIC
                # Validate parameters against the schema
                params = MouseClickParameters.model_validate(action.parameters)
                x = params.x
                y = params.y
                button = params.button
                clicks = params.clicks

                # Map string button to pynput Button object
                from pynput.mouse import Button
                if button == "left":
                    pynput_button = Button.left
                elif button == "right":
                    pynput_button = Button.right
                elif button == "middle":
                    pynput_button = Button.middle
                else:
                    raise ValueError(f"Unknown mouse button: {button}")

                mouse.position = (x, y) # Move mouse to position
                mouse.click(pynput_button, clicks) # Perform click
                
                receipt_status = "success"
                receipt_message = f"Successfully performed {clicks} '{button}' click(s) at ({x}, {y})"
            
            elif action.action_type == "Log":
                message_to_log = action.parameters.get("message")
                if message_to_log:
                    print(f"Actuator Log (Actual Execution): {message_to_log}")
                    receipt_status = "success"
                    receipt_message = f"Successfully logged message: '{message_to_log}'"
                else:
                    receipt_status = "failure"
                    receipt_message = "Log action missing 'message' parameter."
            
            elif action.action_type == "NoAction":
                receipt_status = "success"
                receipt_message = "No action was required or taken."

            else:
                receipt_status = "failure"
                receipt_message = f"Unknown action type for execution: '{action.action_type}'"

        else:
            receipt_status = "failure"
            receipt_message = f"Invalid VerifiedActionPlan status for execution: '{verified_action_plan.status}'"

    except Exception as e:
        receipt_status = "failure"
        receipt_message = f"Execution of action '{action.action_type}' failed: {e}"
        print(f"Actuator ERROR: {receipt_message}")
        
    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000

    return Receipt(
        action_id=action.action_id,
        status=receipt_status,
        message=receipt_message,
        latency_ms=latency_ms,
        origin_observation_id=action.origin_observation_id # Link back to original observation
    )
