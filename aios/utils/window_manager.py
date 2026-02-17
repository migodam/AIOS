import time
import win32gui
import win32process
import win32con
from typing import Optional, Tuple, List

def get_notepad_window_info() -> Tuple[Optional[int], Optional[int]]:
    """
    Finds the HWND and PID of the first Notepad window found.
    Returns (hwnd, pid) or (None, None) if not found.
    """
    target_hwnd = None
    target_pid = None

    def enum_windows_callback(hwnd, extra):
        nonlocal target_hwnd, target_pid
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "Notepad":
            text = win32gui.GetWindowText(hwnd)
            # Ensure it's an actual Notepad instance, not some other window named "Notepad"
            if "notepad" in text.lower(): 
                tid, pid = win32process.GetWindowThreadProcessId(hwnd)
                target_hwnd = hwnd
                target_pid = pid
                return False # Stop enumeration
        return True

    win32gui.EnumWindows(enum_windows_callback, None)
    return target_hwnd, target_pid

def ensure_foreground_window(hwnd: int):
    """
    Attempts to bring the window with the given HWND to the foreground.
    """
    if not win32gui.IsWindow(hwnd):
        print(f"WindowManager: Invalid window handle {hwnd}. Cannot bring to foreground.")
        return

    try:
        # Get the current foreground window
        current_foreground_hwnd = win32gui.GetForegroundWindow()
        
        # If our target window is already foreground, do nothing
        if current_foreground_hwnd == hwnd:
            return

        # Try restoring if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1) # Give it a moment

        # Attempt to bring to foreground using multiple methods
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.1)
        win32gui.BringWindowToTop(hwnd)
        time.sleep(0.1)

        # Verify if it's foreground now
        if win32gui.GetForegroundWindow() != hwnd:
            print(f"WindowManager: Warning: Failed to bring window {hwnd} to foreground reliably.")

    except Exception as e:
        print(f"WindowManager: Error ensuring foreground for window {hwnd}: {e}")

