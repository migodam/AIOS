from __future__ import annotations
import time
from typing import Any, Callable, Dict, Optional, Tuple, Type
from datetime import datetime

from pydantic import BaseModel, ValidationError

from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

from aios.protocols.action_protocol import VerifiedActionPlan
from aios.protocols.schema import (
    Receipt,
    KeyPressParameters,
    TypeStringParameters,
    MouseClickParameters,
    NoActionParameters,
    LogParameters,
)


def _get_key_from_string(key_str: str) -> Any:
    """Maps a string to a pynput Key object or returns the string itself."""
    key_map = {
        "space": Key.space, "enter": Key.enter, "esc": Key.esc, "tab": Key.tab,
        "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        "alt": Key.alt, "ctrl": Key.ctrl, "shift": Key.shift, "win": Key.cmd,
        "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4, "f5": Key.f5, "f6": Key.f6,
        "f7": Key.f7, "f8": Key.f8, "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
        "delete": Key.delete, "backspace": Key.backspace, "caps_lock": Key.caps_lock,
        "num_lock": Key.num_lock, "scroll_lock": Key.scroll_lock, "print_screen": Key.print_screen,
        "home": Key.home, "end": Key.end, "page_up": Key.page_up, "page_down": Key.page_down,
        "insert": Key.insert, "menu": Key.menu, "pause": Key.pause,
    }
    return key_map.get(key_str.lower(), key_str)


def _execute_keypress(params: KeyPressParameters) -> Tuple[str, str]:
    keyboard = KeyboardController()
    
    pynput_modifiers = [_get_key_from_string(k) for k in params.modifiers]
    main_key = _get_key_from_string(params.key)
    
    for mod in pynput_modifiers:
        keyboard.press(mod)
        
    keyboard.press(main_key)
    keyboard.release(main_key)
    
    for mod in reversed(pynput_modifiers):
        keyboard.release(mod)

    # Add a delay for UI to catch up after hotkeys
    if pynput_modifiers:
        time.sleep(5)
        
    return "success", f"Successfully pressed key '{params.key}' with modifiers {params.modifiers}"

def _execute_typestring(params: TypeStringParameters) -> Tuple[str, str]:
    keyboard = KeyboardController()
    
    # Select all (Ctrl+A)
    keyboard.press(Key.ctrl)
    keyboard.press('a')
    keyboard.release('a')
    keyboard.release(Key.ctrl)
    time.sleep(0.1) # Short delay for OS to process selection

    # Delete selected text
    keyboard.press(Key.delete)
    keyboard.release(Key.delete)
    time.sleep(0.1) # Short delay for OS to process deletion
    
    for char in params.text:
        keyboard.type(char)
        time.sleep(0.01) # Small delay after each character
    return "success", f"Successfully typed string: '{params.text}'"

def _execute_mouse_click(params: MouseClickParameters) -> Tuple[str, str]:
    mouse = MouseController()
    button_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
    pynput_button = button_map.get(params.button.lower())
    
    if pynput_button is None:
        raise ValueError(f"Invalid mouse button '{params.button}'.")

    mouse.position = (params.x, params.y)
    mouse.click(pynput_button, params.clicks)
    return "success", f"Successfully clicked {params.button} button {params.clicks} time(s) at ({params.x}, {params.y})"

def _execute_no_action(params: NoActionParameters) -> Tuple[str, str]:
    return "success", params.message or "No action was required or taken."

def _execute_log(params: LogParameters) -> Tuple[str, str]:
    print(f"Actuator Log: {params.message}")
    return "success", f"Successfully logged message: '{params.message}'"


HANDLER_MAP: Dict[str, Tuple[Callable[..., Tuple[str, str]], Type[BaseModel]]] = {
    "KeyPress": (_execute_keypress, KeyPressParameters),
    "TypeString": (_execute_typestring, TypeStringParameters),
    "MouseClick": (_execute_mouse_click, MouseClickParameters),
    "NoAction": (_execute_no_action, NoActionParameters),
    "Log": (_execute_log, LogParameters),
}

def execute_action(verified_action: VerifiedActionPlan) -> Receipt:
    start_time = time.perf_counter()
    action = verified_action.action_plan
    status, message, error = "failed", f"Unknown action type: '{action.action_type}'", None

    if action.action_type in HANDLER_MAP:
        handler, params_class = HANDLER_MAP[action.action_type]
        
        params_obj = action.parameters
        if not isinstance(params_obj, params_class):
            status = "rejected_unsafe"
            message = f"Internal error: parameters for {action.action_type} were not a validated model."
            error = {"type": "TypeError", "message": message, "retryable": False}
        else:
            try:
                print(f"Actuator: Executing action '{action.action_type}'...")
                status, message = handler(params_obj)
            except Exception as e:
                message = f"Execution of action '{action.action_type}' failed: {e}"
                error = {"type": type(e).__name__, "message": str(e), "retryable": False}
                print(f"Actuator ERROR: {message}")
    else:
        error = {"type": "ActionTypeError", "message": message, "retryable": False}

    latency_ms = (time.perf_counter() - start_time) * 1000
    
    return Receipt(
        action_id=action.action_id,
        status=status,
        message=message,
        latency_ms=latency_ms,
        error=error,
    )
