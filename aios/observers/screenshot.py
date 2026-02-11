import hashlib
from pathlib import Path
from datetime import datetime
import mss

from aios.protocols.schema import RawSignal, ScreenshotData

def capture_screenshot(artifact_dir: Path) -> RawSignal:
    """
    Captures a screenshot of the primary monitor using MSS.

    Args:
        artifact_dir: The root directory to save artifacts in. A "screenshots"
                      subdirectory will be created here.

    Returns:
        A populated RawSignal object containing the screenshot data and metadata.
    """
    try:
        # 1. Define artifact path and ensure directory exists
        screenshot_dir = artifact_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate a unique filename
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        file_path = screenshot_dir / f"{timestamp_str}.png"

        # 2. Capture the screenshot
        with mss.mss() as sct:
            # Get information of monitor 1
            monitor_info = sct.monitors[1]
            
            # Grab the data
            sct_img = sct.grab(monitor_info)
            
            # Save to the picture file
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(file_path))
            print(f"Screenshot saved to {file_path}")

        # 3. Calculate SHA256 hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        artifact_hash = sha256_hash.hexdigest()
        print(f"Artifact hash: {artifact_hash}")

        # 4. Populate Pydantic models
        screenshot_data = ScreenshotData(
            format="png",
            screen_size=(sct_img.width, sct_img.height)
        )

        raw_signal = RawSignal(
            observer_id="screenshot_observer_v1",
            artifact_path=str(file_path),
            artifact_hash=artifact_hash,
            data=screenshot_data
        )

        return raw_signal

    except Exception as e:
        print(f"An error occurred during screenshot capture: {e}")
        # In a real scenario, you might want to return a failed signal
        # or raise the exception. For now, we print and return None.
        raise

