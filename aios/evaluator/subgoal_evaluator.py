import re
import win32gui # NEW IMPORT
from typing import Any, Dict, Optional

class SubgoalEvaluator:
    def __init__(self, expected_typed_text: str):
        self.expected_typed_text = expected_typed_text.lower()

    def _parse_done_when_condition(self, done_when_string: str) -> Dict[str, Any]:
        parsed_conditions = {}
        s = done_when_string.lower()

        # Check for notepad open/closed
        if "notepad" in s and ("open" in s or "visible" in s or "foreground" in s):
            parsed_conditions["notepad_status"] = "open"
        elif "notepad" in s and ("closed" in s or "no longer visible" in s):
            parsed_conditions["notepad_status"] = "closed"

        # Check for specific text content
        text_match = re.search(r"contains the text '(.*?)'", s)
        if text_match:
            parsed_conditions["text_to_find"] = text_match.group(1).lower()
        elif "contains a greeting" in s or "equivalent greeting" in s:
            parsed_conditions["text_to_find"] = self.expected_typed_text # Use overall expected text
        
        # Check for focus
        if "in focus" in s or "foreground" in s or "active" in s:
            parsed_conditions["check_focus"] = True

        # Check for new file / no save prompt
        if "new file" in s or "fresh editable document" in s:
            parsed_conditions["new_file_state"] = True
        if "no save prompt" in s or "declined saving" in s:
            parsed_conditions["no_save_prompt"] = True
            
        return parsed_conditions

    def is_done(self, subgoal_id: str, checklist: Dict[str, Any], ui_summary: str, readback_text: str, target_hwnd: Optional[int]) -> bool:
        ui_summary_lower = ui_summary.lower()
        readback_text_lower = readback_text.lower()
        
        # Default behavior for text_present
        text_present = checklist.get("text_present", False)

        # Parse the 'done_when' condition for the current subgoal (assuming it's available)
        # This will be done in TaskLoopController for the current_subgoal
        
        # Handle specific hardcoded checks for now, but this will be generalized
        if subgoal_id == "open_notepad" or subgoal_id == "launch_notepad":
            # Check if Notepad is opened AND is in foreground (if we have a target)
            is_opened = checklist.get("notepad_opened", False)
            if target_hwnd and is_opened:
                return is_opened and win32gui.GetForegroundWindow() == target_hwnd
            return is_opened
        
        elif subgoal_id == "focus_notepad" or subgoal_id == "focus_notepad_window":
            # Check if Notepad is opened AND the targeted Notepad is the foreground window
            return checklist.get("notepad_opened", False) and \
                   (target_hwnd is not None and win32gui.GetForegroundWindow() == target_hwnd)
        
        elif subgoal_id == "new_file":
            # Assuming Ctrl+N has been pressed, check for absence of save dialog
            return checklist.get("notepad_opened", False) and \
                   not ("save changes to untitled" in ui_summary_lower or "是否将更改保存到" in ui_summary_lower or "file open" in ui_summary_lower)

        elif subgoal_id == "type_text" or subgoal_id == "enter_text" or subgoal_id == "type_greeting":
            # This check uses the 'text_present' flag which is set by clipboard readback in TaskLoopController
            return text_present
        
        elif subgoal_id == "close_notepad" or subgoal_id == "close_notepad_without_saving" or subgoal_id == "discard_changes":
            # Subgoal is done if notepad is no longer detected as open
            return not checklist.get("notepad_opened", True)
        
        elif subgoal_id == "choose_not_to_save":
            # This subgoal implies a save dialog was present and now it's gone.
            # So, if Notepad is closed, this subgoal is done.
            return not checklist.get("notepad_opened", True) and \
                   not ("save changes to untitled" in ui_summary_lower or "是否将更改保存到" in ui_summary_lower)

        return False
