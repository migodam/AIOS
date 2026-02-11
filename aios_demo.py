import uuid
import subprocess
import time
from pathlib import Path
import sys
from datetime import datetime # Added import

# Ensure the project root is on the Python path for imports
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from aios.protocols.schema import (
    Event,
    EventType,
)
from aios.event_stream import JsonlLogger
from aios.memory.graph import GraphMemory
from aios.observers.screenshot import capture_screenshot
from aios.observers.uia import get_focused_uia_tree
from aios.protocols.llm_connector import call_llm_api
from aios.agent.main_agent import decide_action
from aios.protocols.action_protocol import process_action_plan
from aios.actuators.main_actuator import execute_action

def run_aios_cycle(run_id: str, artifact_base_dir: Path, launch_notepad: bool = True):
    """
    Executes one full cycle of the AIOS: Observe -> Parse -> Learn -> Decide -> Plan -> Act.
    """
    print(f"\n--- Starting AIOS Cycle: {run_id} ---")

    # Define paths for artifacts for this specific run
    run_artifact_dir = artifact_base_dir / run_id
    run_artifact_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = run_artifact_dir / "events.jsonl"
    graph_file_path = run_artifact_dir / "graph_memory.json"
    artifacts_path = run_artifact_dir / "artifacts"
    artifacts_path.mkdir(exist_ok=True)
    
    notepad_process = None
    if launch_notepad:
        # 1. Launch notepad as a predictable GUI target
        print("\nStep 1: Launching Notepad...")
        notepad_process = subprocess.Popen(["notepad.exe"])
        try:
            # Wait for notepad to open and hopefully gain focus
            time.sleep(5) # Increased sleep for robustness
            print("Notepad launched.")

            # 2. Initialize Components
            print("\nStep 2: Initializing logger and graph memory...")
            logger = JsonlLogger(log_file_path)
            graph = GraphMemory(graph_file_path)

            # 3. Run Observers
            print("\nStep 3: Running observers (Screenshot and UIA)...")
            raw_signals = []
            try:
                screenshot_signal = capture_screenshot(artifacts_path)
                print(f"Successfully captured screenshot.")
                raw_signals.append(screenshot_signal)
            except Exception as e:
                print(f"Screenshot capture failed: {e}")

            try:
                # We use max_depth=8 for robustness in pilot script
                uia_signal = get_focused_uia_tree(artifacts_path, max_depth=8) # Increased max_depth
                print(f"Successfully captured UIA tree for '{uia_signal.data.focused_window_title}'.")
                raw_signals.append(uia_signal)
            except Exception as e:
                print(f"UIA tree capture failed: {e}")

            if not raw_signals:
                print("No raw signals collected. Skipping further steps.")
                return False # Indicate failure to collect signals

            # 4. Process Raw Signals with LLM Connector (Mock Mode)
            print("\nStep 4: Processing raw signals with LLM Connector (Mock Mode)...")
            observation = call_llm_api(raw_signals, use_mock=True)
            print(f"LLM Connector (Mock) produced ObservationEvent (ID: {observation.observation_id}).")

            # 5. Wrap and Log Observation Event
            print("\nStep 5: Wrapping and logging observation event...")
            event_obs = Event(event_id=str(uuid.uuid4()), event_type=EventType.OBSERVATION, payload=observation)
            logger.log_event(event_obs)

            # 6. Update Graph Memory with the new observation
            print("\nStep 6: Updating graph memory with observation...")
            graph.update(observation)
            graph.save()

            # 7. Agent Decision-Making
            print("\nStep 7: Agent deciding action...")
            action_plan = decide_action(observation, graph) # Pass the current graph
            print(f"Agent produced ActionPlan (Type: {action_plan.action_type}).")

            # 8. Wrap and Log ActionPlan Event
            print("\nStep 8: Wrapping and logging action plan event...")
            event_action = Event(event_id=str(uuid.uuid4()), event_type=EventType.ACTION, payload=action_plan)
            logger.log_event(event_action)

            # 9. Protocol2 Action Planning
            print("\nStep 9: Protocol2 processing ActionPlan...")
            verified_action_plan = process_action_plan(action_plan)
            print(f"Protocol2 produced VerifiedActionPlan (Status: {verified_action_plan.status}).")

            # 10. Wrap and Log VerifiedActionPlan Event (using ACTION type, but payload is VAP)
            print("\nStep 10: Wrapping and logging verified action plan event...")
            event_verified_action = Event(
                event_id=str(uuid.uuid4()), 
                event_type=EventType.ACTION, # Using ACTION type, payload is ActionPlan from VerifiedActionPlan
                payload=verified_action_plan.action_plan 
            )
            logger.log_event(event_verified_action)

            # 11. Actuator Execution
            print("\nStep 11: Actuator executing action...")
            if verified_action_plan.action_plan.action_type == "TypeString" and verified_action_plan.status == "ready_for_execution":
                print(">>> Please ensure Notepad is focused and ready to receive keyboard input <<<")
                time.sleep(1) # Give user a moment to focus Notepad if needed
            receipt = execute_action(verified_action_plan)
            print(f"Actuator produced Receipt (Status: {receipt.status}, Message: {receipt.message}).")

            # 12. Wrap and Log Receipt Event
            print("\nStep 12: Wrapping and logging receipt event...")
            event_receipt = Event(event_id=str(uuid.uuid4()), event_type=EventType.RECEIPT, payload=receipt)
            logger.log_event(event_receipt)
            
            # 13. Verification - simplified for demo
            print(f"\n--- AIOS Cycle: {run_id} Completed Successfully ---")
            return True # Indicate success

        finally:
            # 14. Clean up the notepad process
            if notepad_process:
                print("\nStep 14: Terminating Notepad...")
                notepad_process.terminate()
                notepad_process.wait()
                print("Notepad terminated.")
    else:
        print("Skipping Notepad launch for this run.")
        # Minimal cycle for demonstration purposes without UI interaction
        print(f"\n--- AIOS Cycle: {run_id} Completed (No Notepad) ---")
        return True # Indicate success
    
    return False # Indicate failure if execution didn't reach success path

if __name__ == "__main__":
    # Create a unique run ID for this demonstration
    demo_run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_artifact_dir = Path("./aios_demo_runs") # Store demo artifacts in a dedicated directory

    print("--- Preparing AIOS Demo ---")
    print(f"Demo artifacts will be stored in: {base_artifact_dir / demo_run_id}")
    print("AIOS Demo will start in 5 seconds. Ensure no critical work is open, Notepad will launch and text will be typed...")
    time.sleep(5) # Auto-start after a pause
    
    run_aios_cycle(demo_run_id, base_artifact_dir, launch_notepad=True)
    print("\nAIOS Demo Finished.")
    print(f"Check logs and artifacts in {base_artifact_dir / demo_run_id}")