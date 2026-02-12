import uuid
import subprocess
import time
from pathlib import Path
import sys
from datetime import datetime
import argparse # ADDED

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

def run_aios_cycle(run_id: str, artifact_base_dir: Path, user_instruction: str = "", llm_use_mock: bool = True, llm_api_key: str = None):
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
    
    try: # Added try block
        # 1. Initialize Components
        print("\nStep 1: Initializing logger and graph memory...")
        logger = JsonlLogger(log_file_path)
        graph = GraphMemory(graph_file_path)

        # 2. Run Observers
        print("\nStep 2: Running observers (Screenshot and UIA)...")
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

        # 3. Process Raw Signals with LLM Connector
        print("\nStep 3: Processing raw signals with LLM Connector...")
        # Pass user_instruction and use_mock from function arguments
        observation = call_llm_api(raw_signals, user_instruction=user_instruction, use_mock=llm_use_mock)
        print(f"LLM Connector produced ObservationEvent (ID: {observation.observation_id}).")

        # 4. Wrap and Log Observation Event
        print("\nStep 4: Wrapping and logging observation event...")
        event_obs = Event(event_id=str(uuid.uuid4()), event_type=EventType.OBSERVATION, payload=observation)
        logger.log_event(event_obs)

        # 5. Update Graph Memory with the new observation
        print("\nStep 5: Updating graph memory with observation...")
        graph.update(observation)
        graph.save()

        # 6. Agent Decision-Making
        print("\nStep 6: Agent deciding action...")
        action_plan = decide_action(observation, graph) # Pass the current graph
        print(f"Agent produced ActionPlan (Type: {action_plan.action_type}).")

        # 7. Wrap and Log ActionPlan Event
        print("\nStep 7: Wrapping and logging action plan event...")
        event_action = Event(event_id=str(uuid.uuid4()), event_type=EventType.ACTION, payload=action_plan)
        logger.log_event(event_action)

        # 8. Protocol2 Action Planning
        print("\nStep 8: Protocol2 processing ActionPlan...")
        verified_action_plan = process_action_plan(action_plan)
        print(f"Protocol2 produced VerifiedActionPlan (Status: {verified_action_plan.status}).")

        # 9. Wrap and Log VerifiedActionPlan Event (using ACTION type, but payload is VAP)
        print("\nStep 9: Wrapping and logging verified action plan event...")
        event_verified_action = Event(
            event_id=str(uuid.uuid4()), 
            event_type=EventType.ACTION, # Using ACTION type, payload is ActionPlan from VerifiedActionPlan
            payload=verified_action_plan.action_plan 
        )
        logger.log_event(event_verified_action)

        # 10. Actuator Execution
        print("\nStep 10: Actuator executing action...")
        # Added prompt for Dino game if a jump action is planned
        if (verified_action_plan.action_plan.action_type == "KeyPress" and 
            verified_action_plan.action_plan.parameters.get("key") == "space" and
            verified_action_plan.status == "ready_for_execution"):
            print(">>> Please ensure the Chrome Dino game window is focused and ready to receive keyboard input (spacebar to jump) <<<")
            time.sleep(1) # Give user a moment to focus the window

        receipt = execute_action(verified_action_plan)
        print(f"Actuator produced Receipt (Status: {receipt.status}, Message: {receipt.message}).")

        # 11. Wrap and Log Receipt Event
        print("\nStep 11: Wrapping and logging receipt event...")
        event_receipt = Event(event_id=str(uuid.uuid4()), event_type=EventType.RECEIPT, payload=receipt)
        logger.log_event(event_receipt)
        
        # 12. Verification - simplified for demo
        print(f"\n--- AIOS Cycle: {run_id} Completed Successfully ---")
        return True # Indicate success

    except Exception as e: # Catch any exceptions during the cycle
        print(f"AIOS Cycle {run_id} failed: {e}")
        return False # Indicate failure

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AIOS Demo Cycle.")
    parser.add_argument("--user_instruction", type=str, default="Demonstrating AIOS basic cycle",
                        help="User instruction for the AIOS agent.")
    parser.add_argument("--llm_use_mock", type=lambda x: x.lower() == 'true', default=True,
                        help="Use mock LLM responses (True/False).")
    parser.add_argument("--llm_api_key", type=str, default=None,
                        help="Optional LLM API Key.")

    args = parser.parse_args()

    # Create a unique run ID for this demonstration
    demo_run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_artifact_dir = Path("./aios_demo_runs") # Store demo artifacts in a dedicated directory

    print("--- Preparing AIOS Demo ---")
    print(f"Demo artifacts will be stored in: {base_artifact_dir / demo_run_id}")
    print("AIOS Demo will start in 5 seconds. Ensure no critical work is open.")
    time.sleep(5) # Auto-start after a pause
    
    run_aios_cycle(demo_run_id, base_artifact_dir, 
                   user_instruction=args.user_instruction, 
                   llm_use_mock=args.llm_use_mock, 
                   llm_api_key=args.llm_api_key)
    print("\nAIOS Demo Finished.")
    print(f"Check logs and artifacts in {base_artifact_dir / demo_run_id}")