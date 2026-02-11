import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

import comtypes.client
from comtypes import IUnknown, CoCreateInstance, COMError
from comtypes.gen import UIAutomationClient as uia
import win32process # New import

from aios.protocols.schema import RawSignal, UIATreeData # Added ScreenshotData for empty signal

# --- Helper Functions ---

def get_uia_properties(element: IUnknown) -> Dict[str, Any]:
    """Extracts serializable properties from a UI Automation element."""
    try:
        rect = element.CurrentBoundingRectangle
        bounding_rect = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except COMError:
        bounding_rect = (0, 0, 0, 0)

    try:
        process_id = element.CurrentProcessId
    except COMError:
        process_id = -1
        
    return {
        "name": element.CurrentName or "",
        "control_type": element.CurrentControlType,
        "automation_id": element.CurrentAutomationId or "",
        "class_name": element.CurrentClassName or "",
        "process_id": process_id,
        "is_enabled": element.CurrentIsEnabled,
        "is_keyboard_focusable": element.CurrentIsKeyboardFocusable,
        "bounding_rectangle": bounding_rect,
    }

def walk_uia_tree(element: IUnknown, uia_instance: IUnknown, max_depth: int) -> Dict[str, Any] | None:
    """
    Recursively walks the UIA tree from a given element using a pre-created uia_instance.
    """
    if not element or max_depth <= 0:
        return None

    try:
        node = get_uia_properties(element)
        node["children"] = []
        
        walker = uia_instance.ControlViewWalker
        
        child = walker.GetFirstChildElement(element)
        while child:
            child_node = walk_uia_tree(child, uia_instance, max_depth - 1)
            if child_node:
                node["children"].append(child_node)
            child = walker.GetNextSiblingElement(child)
            
        return node
    except (COMError, OSError) as e: # OSError can happen on stale elements
        print(f"Error while walking UIA tree for element: {e}")
        return None

# --- Main Observer Function ---

def get_focused_uia_tree(artifact_dir: Path, max_depth: int = 5) -> RawSignal:
    """
    Captures the UIA tree of the Notepad window (if found) and packages it
    into a RawSignal. Falls back to focused element if Notepad not found.

    Args:
        artifact_dir: The root directory to save artifacts in.
        max_depth: The maximum depth to traverse the UIA tree.

    Returns:
        A RawSignal object containing the UIA tree data, or a dummy if no Notepad found.
    """
    try:
        uia_instance = CoCreateInstance(uia.CUIAutomation._reg_clsid_, interface=uia.IUIAutomation, clsctx=comtypes.CLSCTX_INPROC_SERVER)
        desktop_root = uia_instance.GetRootElement()
        
        # --- Explicitly search for Notepad ---
        notepad_condition = uia_instance.CreatePropertyCondition(uia.UIA_ClassNamePropertyId, "Notepad")
        notepad_elements = desktop_root.FindAll(uia.TreeScope_Descendants, notepad_condition)
        
        target_element = None
        focused_window_title = "Unknown (No Notepad Found)"
        
        if notepad_elements.Length > 0:
            target_element = notepad_elements.GetElement(0) # Get the first Notepad window
            focused_window_title = target_element.CurrentName or "Untitled - Notepad"
            print(f"UIA Observer: Found Notepad window: '{focused_window_title}'")
        else:
            print("UIA Observer: Notepad window not found by class name. Falling back to focused element.")
            focused_element = uia_instance.GetFocusedElement()
            if focused_element:
                target_element = focused_element
                focused_window_title = target_element.CurrentName or "Unknown (No Focus)"
            else:
                print("UIA Observer: No focused element found. Falling back to desktop root.")
                target_element = uia_instance.GetRootElement()
                focused_window_title = target_element.CurrentName or "Desktop Root"

        if not target_element:
            print("UIA Observer: Could not find any target element. Returning empty RawSignal.")
            return RawSignal(
                observer_id="uia_observer_v1_empty",
                artifact_path="",
                artifact_hash="",
                data=UIATreeData(focused_window_title="Empty UIA Signal", tree_structure={})
            )
            
        tree_structure = walk_uia_tree(target_element, uia_instance, max_depth)
        if not tree_structure:
            raise RuntimeError("Failed to walk the UIA tree for target element.")

        # Serialize and save artifact
        uia_dir = artifact_dir / "uia_trees"
        uia_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        file_path = uia_dir / f"{timestamp_str}.json"
        
        json_str = json.dumps(tree_structure, indent=4)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"UIA tree saved to {file_path}")

        # Calculate hash from the file
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        artifact_hash = sha256_hash.hexdigest()
        print(f"Artifact hash: {artifact_hash}")

        # Populate Pydantic models
        uia_data = UIATreeData(
            focused_window_title=focused_window_title,
            tree_structure=tree_structure
        )

        raw_signal = RawSignal(
            observer_id="uia_observer_v1",
            artifact_path=str(file_path),
            artifact_hash=artifact_hash,
            data=uia_data
        )

        return raw_signal

    except Exception as e:
        print(f"An error occurred during UIA tree capture: {e}. Returning empty RawSignal.")
        # Return an empty RawSignal to allow the pipeline to continue
        return RawSignal(
            observer_id="uia_observer_v1_error",
            artifact_path="",
            artifact_hash="",
            data=UIATreeData(focused_window_title=f"Error: {e}", tree_structure={})
        )
