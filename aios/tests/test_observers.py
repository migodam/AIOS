import hashlib
from pathlib import Path
import pytest
import subprocess
import time
import os
from typing import Any, Dict

# Conditional import for Windows-specific modules
try:
    import win32gui
    import win32con
    import win32process
    import win32com.client
    import comtypes
    from comtypes import CoCreateInstance
    from comtypes.gen import UIAutomationClient as uia
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

from aios.observers.screenshot import capture_screenshot
from aios.protocols.schema import RawSignal, ScreenshotData, UIATreeData
# Import the core walking function for direct testing
from aios.observers.uia import walk_uia_tree

@pytest.mark.skipif(not IS_WINDOWS, reason="Screenshot observer test is for Windows")
def test_capture_screenshot(tmp_path: Path):
    """
    Tests the capture_screenshot function.
    """
    artifact_dir = tmp_path / "artifacts"
    try:
        raw_signal = capture_screenshot(artifact_dir)
    except Exception as e:
        if "Xlib" in str(e) or "Display" in str(e):
             pytest.skip(f"Skipping screenshot test in headless environment: {e}")
        raise

    assert isinstance(raw_signal, RawSignal)
    assert raw_signal.observer_id == "screenshot_observer_v1"
    assert isinstance(raw_signal.data, ScreenshotData)
    
    artifact_path = Path(raw_signal.artifact_path)
    assert artifact_path.exists() and artifact_path.stat().st_size > 0
    
    sha256_hash = hashlib.sha256()
    with open(artifact_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    recalculated_hash = sha256_hash.hexdigest()
    
    assert raw_signal.artifact_hash == recalculated_hash

def find_node_by_pid(tree: Dict[str, Any], pid: int) -> Dict[str, Any] | None:
    """Recursively searches a UIA tree for a node with a specific PID."""
    if tree.get("process_id") == pid:
        return tree
    for child in tree.get("children", []):
        found = find_node_by_pid(child, pid)
        if found:
            return found
    return None

@pytest.mark.skipif(not IS_WINDOWS, reason="UIA observer test is for Windows")
def test_uia_tree_observer_can_find_known_process(tmp_path: Path):
    """
    Tests the core UIA walking logic by searching for a known, stable
    system process (explorer.exe) in a full desktop tree scan.
    """
    # 1. Find the PID of explorer.exe using WMI (more reliable)
    wmi = win32com.client.GetObject("winmgmts:")
    processes = wmi.InstancesOf("Win32_Process")
    explorer_pids = [p.ProcessId for p in processes if p.Name == "explorer.exe"]
    assert explorer_pids, "Could not find PID for explorer.exe using WMI."
    explorer_pid = explorer_pids[0]

    # 2. Get the desktop root element and uia_instance
    uia_instance = CoCreateInstance(
        uia.CUIAutomation._reg_clsid_, 
        interface=uia.IUIAutomation, 
        clsctx=comtypes.CLSCTX_INPROC_SERVER
    )
    desktop_root = uia_instance.GetRootElement()
    assert desktop_root, "Failed to get UIA desktop root element."

    # 3. Execute the core tree walking function on the whole desktop
    desktop_tree = walk_uia_tree(desktop_root, uia_instance, max_depth=8)
    assert desktop_tree is not None, "walk_uia_tree returned None for desktop."

    # 4. Search for the explorer.exe process within the captured tree
    explorer_node = find_node_by_pid(desktop_tree, explorer_pid)
    
    # 5. Assert that the explorer.exe process was found
    assert explorer_node is not None, f"Could not find node with explorer.exe PID {explorer_pid} in the UIA tree."
    
    print(f"Successfully found explorer.exe node in UIA tree: {explorer_node.get('name')}")
