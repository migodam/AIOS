import win32clipboard
import win32con
import time
from typing import Optional

def get_clipboard_text() -> Optional[str]:
    """
    Retrieves text from the clipboard.
    Returns the text as a string, or None if the clipboard does not contain text.
    """
    try:
        win32clipboard.OpenClipboard(None)
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return data
        return None
    except Exception as e:
        print(f"ClipboardManager: Error getting clipboard text: {e}")
        return None
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"ClipboardManager: Error closing clipboard: {e}")

def clear_clipboard():
    """
    Clears the clipboard.
    """
    try:
        win32clipboard.OpenClipboard(None)
        win32clipboard.EmptyClipboard()
    except Exception as e:
        print(f"ClipboardManager: Error clearing clipboard: {e}")
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"ClipboardManager: Error closing clipboard: {e}")

