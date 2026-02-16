from __future__ import annotations
import time
from typing import Any, Dict
from datetime import datetime

from typing import Optional # ADDED
import re # For hotkey parsing

# Import pynput for keyboard control
from pynput.keyboard import Controller as KeyboardController, Key # ADDED Key for direct import
from pynput.mouse import Controller as MouseController # ADDED

from aios.protocols.schema import Receipt, EventType, Event, ActionPlan # Removed direct import of parameter schemas as they will be normalized
from aios.protocols.action_protocol import VerifiedActionPlan
from aios.utils.params import normalize_params # ADDED


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
    
    receipt_status = "failed" # Default to failed
    receipt_message = "Action could not be executed due to an unexpected error."
    error_info: Optional[Dict[str, Any]] = None # To store detailed error info

    try:
        if verified_action_plan.status == "rejected_unsafe":
            receipt_status = "rejected_unsafe"
            receipt_message = verified_action_plan.validation_messages[0] if verified_action_plan.validation_messages else "Action was rejected by Protocol2 as unsafe."
            error_info = {"type": "Validation Error", "message": receipt_message, "retryable": False}
            print(f"Actuator: {receipt_message}")
        
        elif verified_action_plan.status == "dry_run_completed":
            receipt_status = "dry_run_success"
            receipt_message = f"Action completed successfully in dry-run mode. Preview: {verified_action_plan.actuator_preview}"
            print(f"Actuator: {receipt_message}")

        elif verified_action_plan.status == "ready_for_execution":
            print(f"Actuator: Executing action '{action.action_type}' (ID: {action.action_id})...")
            keyboard = KeyboardController()
            mouse = MouseController()
            
            # Normalize parameters
            normalized_params = normalize_params(action.parameters)

            if action.action_type == "TypeString":
                text_to_type = normalized_params.get("text")
                enter_after = normalized_params.get("enter_after", False)
                if text_to_type is not None:
                    keyboard.type(str(text_to_type))
                    if enter_after:
                        keyboard.press(Key.enter)
                        keyboard.release(Key.enter)
                    receipt_status = "success"
                    receipt_message = f"Successfully typed: '{text_to_type}' (Enter after: {enter_after})"
                else:
                    receipt_status = "failed"
                    receipt_message = "TypeString action missing required 'text' parameter."
                    error_info = {"type": "Parameter Error", "message": receipt_message, "retryable": False}
            
            elif action.action_type == "KeyPress":
                keys_to_press = normalized_params.get("keys")
                key_to_press = normalized_params.get("key")
                hotkey_to_press = normalized_params.get("hotkey")
                
                # Prioritized parameter extraction
                if keys_to_press and isinstance(keys_to_press, list):
                    all_keys = keys_to_press
                elif hotkey_to_press and isinstance(hotkey_to_press, str):
                    # Parse hotkey string (e.g., "win+r", "ctrl+alt+del")
                    all_keys = [k.strip().lower() for k in hotkey_to_press.split('+')]
                elif key_to_press and isinstance(key_to_press, str):
                    all_keys = [key_to_press.lower()]
                else:
                    receipt_status = "failed"
                    receipt_message = "KeyPress action missing required 'keys', 'key', or 'hotkey' parameter."
                    error_info = {"type": "Parameter Error", "message": receipt_message, "retryable": False}
                    raise ValueError(receipt_message) # Raise to catch below

                actual_pynput_keys = []
                modifiers_pressed = []

                # Map special key names to pynput.keyboard.Key objects
                key_mapping = {
                    "space": Key.space, "enter": Key.enter, "esc": Key.esc, "tab": Key.tab,
                    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
                    "alt": Key.alt, "ctrl": Key.ctrl, "shift": Key.shift, "win": Key.cmd, # 'cmd' for Windows key
                    "f1": Key.f1, "f2": Key.f3, "f4": Key.f4, "f5": Key.f5, "f6": Key.f6,
                    "f7": Key.f7, "f8": Key.f8, "f9": Key.f9, "f10": Key.f10,
                    "f11": Key.f11, "f12": Key.f12,
                    "delete": Key.delete, "backspace": Key.backspace, "caps_lock": Key.caps_lock,
                    "num_lock": Key.num_lock, "scroll_lock": Key.scroll_lock, "print_screen": Key.print_screen,
                    "home": Key.home, "end": Key.end, "page_up": Key.page_up, "page_down": Key.page_down,
                    "insert": Key.insert, "menu": Key.menu, "pause": Key.pause
                }

                for k in all_keys:
                    if k in key_mapping:
                        actual_pynput_keys.append(key_mapping[k])
                    elif k in ["alt", "ctrl", "shift", "win"]: # Modifiers if not a special key
                        actual_pynput_keys.append(key_mapping.get(k, k)) # Add as char if not mapped
                    else: # Assume it's a character
                        actual_pynput_keys.append(k)
                
                # Press modifiers first
                for k in actual_pynput_keys[:-1]: # All except the last one are considered modifiers
                    if isinstance(k, Key):
                        keyboard.press(k)
                        modifiers_pressed.append(k)
                    elif isinstance(k, str) and k in key_mapping: # String modifier like 'alt'
                        modifier_key = key_mapping[k]
                        keyboard.press(modifier_key)
                        modifiers_pressed.append(modifier_key)

                # Press and release the main key
                main_key = actual_pynput_keys[-1]
                if isinstance(main_key, Key):
                    keyboard.press(main_key)
                    keyboard.release(main_key)
                else: # Assume it's a character
                    keyboard.type(str(main_key))
                
                # Release modifiers in reverse order
                for mod in reversed(modifiers_pressed):
                    keyboard.release(mod)

                receipt_status = "success"
                receipt_message = f"Successfully pressed key(s): '{all_keys}'"
            
            elif action.action_type == "MouseClick":
                x = normalized_params.get("x")
                y = normalized_params.get("y")
                button_str = normalized_params.get("button", "left")
                clicks = normalized_params.get("clicks", 1)

                if x is None or y is None:
                    receipt_status = "failed"
                    receipt_message = "MouseClick action missing required 'x' or 'y' parameter."
                    error_info = {"type": "Parameter Error", "message": receipt_message, "retryable": False}
                    raise ValueError(receipt_message)

                from pynput.mouse import Button
                button_mapping = {"left": Button.left, "right": Button.right, "middle": Button.middle}
                pynput_button = button_mapping.get(button_str.lower())

                if pynput_button is None:
                    receipt_status = "failed"
                    receipt_message = f"Invalid mouse button: '{button_str}'. Must be 'left', 'right', or 'middle'."
                    error_info = {"type": "Parameter Error", "message": receipt_message, "retryable": False}
                    raise ValueError(receipt_message)

                mouse.position = (x, y)
                mouse.click(pynput_button, clicks)
                
                receipt_status = "success"
                receipt_message = f"Successfully performed {clicks} '{button_str}' click(s) at ({x}, {y})"
            
            elif action.action_type == "Log":
                message_to_log = normalized_params.get("message")
                if message_to_log is not None:
                    print(f"Actuator Log: {message_to_log}")
                    receipt_status = "success"
                    receipt_message = f"Successfully logged message: '{message_to_log}'"
                else:
                    receipt_status = "failed"
                    receipt_message = "Log action missing required 'message' parameter."
                    error_info = {"type": "Parameter Error", "message": receipt_message, "retryable": False}
            
            elif action.action_type == "NoAction":
                receipt_status = "success"
                receipt_message = "No action was required or taken."

            else:
                receipt_status = "failed"
                receipt_message = f"Unknown action type for execution: '{action.action_type}'"
                error_info = {"type": "Action Type Error", "message": receipt_message, "retryable": False}

        else: # This covers rejected_unsafe and dry_run_completed from Protocol2
            receipt_status = verified_action_plan.status
            receipt_message = verified_action_plan.validation_messages[0] if verified_action_plan.validation_messages else f"Action not executed due to status: '{verified_action_plan.status}'"
            if verified_action_plan.status == "rejected_unsafe":
                error_info = {"type": "Validation Error", "message": receipt_message, "retryable": False}
            elif verified_action_plan.status == "dry_run_completed":
                 receipt_message = f"Action completed successfully in dry-run mode. Preview: {verified_action_plan.actuator_preview}" # Override message for dry-run
                 receipt_status = "dry_run_success" # Ensure status is correct for dry-run
            print(f"Actuator: {receipt_message}")

    except Exception as e:
        receipt_status = "failed"
        exception_type = type(e).__name__
        is_retryable = False # Default to non-retryable for generic exceptions

        if isinstance(e, (ValueError, TypeError)):
            # Parameter errors or type mismatches from normalize_params or internal checks
            error_type = "Parameter/Internal Error"
        elif isinstance(e, PermissionError):
            error_type = "Permission Error"
            receipt_message = "Actuator lacks necessary permissions for this action."
        elif isinstance(e, OSError):
            error_type = "OS Error"
        else:
            error_type = exception_type

        # Customize message if it's a generic parameter error from within the actuator
        if "missing required" in str(e) or "invalid parameter" in str(e):
            error_type = "Parameter Error"

        full_error_message = f"Execution of action '{action.action_type}' failed: {e}"
        print(f"Actuator ERROR: {full_error_message}")
        
        error_info = {"type": error_type, "message": full_error_message, "retryable": is_retryable}
        receipt_message = full_error_message # Use detailed message for receipt

    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000

    return Receipt(
        action_id=action.action_id,
        status=receipt_status,
        message=receipt_message,
        latency_ms=latency_ms,
        error=error_info # Include error info here
    )
