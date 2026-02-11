import subprocess
from pathlib import Path

def run_pilot():
    """
    A simple pilot script to run the aios_demo.py.
    """
    print("--- Starting Pilot Script (Running aios_demo.py) ---")
    
    # Get the path to aios_demo.py
    script_dir = Path(__file__).resolve().parent
    demo_script_path = script_dir.parent / "aios_demo.py"

    # Ensure the virtual environment's python is used
    python_executable = Path(".venv/Scripts/python.exe") # Assumes .venv is in project root
    if not python_executable.exists():
        print("Error: Virtual environment not found. Please ensure it's set up correctly.")
        return

    try:
        # Execute aios_demo.py using the venv's python
        result = subprocess.run(
            [str(python_executable), str(demo_script_path)],
            check=True, # Raise an exception for non-zero exit codes
            capture_output=False, # Let the demo script print to stdout directly
            text=True
        )
        print("\n--- aios_demo.py execution completed ---")

    except subprocess.CalledProcessError as e:
        print(f"\n--- ERROR: aios_demo.py failed ---")
        print(f"Stdout:\n{e.stdout}")
        print(f"Stderr:\n{e.stderr}")
        print(f"Exit Code: {e.returncode}")
        
    except FileNotFoundError:
        print(f"Error: Python executable not found at {python_executable}. Is the virtual environment activated or correctly configured?")

if __name__ == "__main__":
    run_pilot()