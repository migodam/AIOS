import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

import comtypes.client
from comtypes import IUnknown, CoCreateInstance, COMError
from comtypes.gen import UIAutomationClient as uia

from aios.protocols.schema import RawSignal, UIATreeData

def get_uia_properties(element: IUnknown) -> Dict[str, Any]:
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
    except (COMError, OSError):
        return None

def get_focused_uia_tree(artifact_dir: Path, max_depth: int = 5) -> RawSignal:
    try:
        uia_instance = CoCreateInstance(uia.CUIAutomation._reg_clsid_, interface=uia.IUIAutomation, clsctx=comtypes.CLSCTX_INPROC_SERVER)
        desktop_root = uia_instance.GetRootElement()
        
        target_element = None
        focused_window_title = "Unknown"

        # Try to find Notepad first
        notepad_condition = uia_instance.CreatePropertyCondition(uia.UIA_ClassNamePropertyId, "Notepad")
        notepad_element = desktop_root.FindFirst(uia.TreeScope_Children, notepad_condition)
        if notepad_element:
            target_element = notepad_element
            focused_window_title = target_element.CurrentName or "Notepad"
        else:
            # More robust search for Run dialog: look for class name #32770 (dialog)
            # and then check if its name contains "Run" (or localized equivalent)
            dialog_condition = uia_instance.CreatePropertyCondition(uia.UIA_ClassNamePropertyId, "#32770")
            dialog_elements = desktop_root.FindAll(uia.TreeScope_Children, dialog_condition)
            
            run_found = False
            for i in range(dialog_elements.Length):
                dialog_element = dialog_elements.GetElement(i)
                if "run" in (dialog_element.CurrentName or "").lower() or "运行" in (dialog_element.CurrentName or "").lower():
                    target_element = dialog_element
                    focused_window_title = target_element.CurrentName or "Run"
                    run_found = True
                    break
            
            if not run_found:
                # Fallback to the currently focused element
                focused_element = uia_instance.GetFocusedElement()
                if focused_element:
                    target_element = focused_element
                    focused_window_title = target_element.CurrentName or "Focused Element"
                else:
                    # If nothing is focused, use the desktop root
                    target_element = desktop_root
                    focused_window_title = "Desktop"
        
        tree_structure = walk_uia_tree(target_element, uia_instance, max_depth)
        if not tree_structure:
            tree_structure = {"error": "Failed to walk UIA tree."}

        uia_dir = artifact_dir / "uia_trees"
        uia_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        file_path = uia_dir / f"{timestamp_str}.json"
        
        json_str = json.dumps(tree_structure, indent=4)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        artifact_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest() # Moved this line

        return RawSignal(
            observer_id="uia_observer_v2",
            artifact_path=str(file_path),
            artifact_hash=artifact_hash,
            data=UIATreeData(
                focused_window_title=focused_window_title,
                tree_structure=tree_structure
            )
        )
    except Exception as e:
        return RawSignal(
            observer_id="uia_observer_v2_error",
            artifact_path="",
            artifact_hash="",
            data=UIATreeData(focused_window_title=f"Error: {e}", tree_structure={})
        )
