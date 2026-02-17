import uuid
import subprocess
import time
from pathlib import Path
import sys
from datetime import datetime
import argparse
import os
from types import SimpleNamespace

# Ensure the project root is on the Python path
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# AIOS Core Imports
from aios.protocols.schema import (
    Event, EventType, ActionPlan, TaskState, TaskResult,
    ObservationEvent, KeyPressParameters, TypeStringParameters
)
from aios.protocols.action_protocol import VerifiedActionPlan, process_action_plan
from aios.event_stream import JsonlLogger
from aios.memory.graph import GraphMemory
from aios.observers.screenshot import capture_screenshot
from aios.observers.uia import get_focused_uia_tree
from aios.actuators.main_actuator import execute_action as real_execute_action
from aios.llm.llm_client import LLMClient
from aios.task_loop import TaskLoopController, CompletionJudge

# This is the corrected flow. The actuator now uses the protocol.
def combined_protocol_and_actuator(action_plan: ActionPlan) -> VerifiedActionPlan:
    """
    A single function that encapsulates the action protocol and actuator execution.
    It's a simplified placeholder for a more robust component interaction.
    """
    verified_plan = process_action_plan(action_plan)
    if verified_plan.status == "ready_for_execution":
        return real_execute_action(verified_plan)
    else:
        # If the plan was rejected, create a receipt from the validation messages
        from aios.protocols.schema import Receipt
        return Receipt(
            action_id=action_plan.action_id,
            status=verified_plan.status,
            message=verified_plan.validation_messages[0] if verified_plan.validation_messages else "Action rejected."
        )

# A simple observer placeholder
class DemoObserver:
    def __init__(self, artifacts_path: Path):
        self.artifacts_path = artifacts_path

    def observe(self) -> ObservationEvent:
        screenshot_signal = capture_screenshot(self.artifacts_path)
        uia_signal = get_focused_uia_tree(self.artifacts_path)
        
        ui_summary = "No UI summary"
        if uia_signal and uia_signal.data:
            ui_summary = f"Focused Window: {uia_signal.data.focused_window_title}"

        return ObservationEvent(
            observation_id=str(uuid.uuid4()),
            raw_signals=[screenshot_signal, uia_signal],
            ui_state_summary=ui_summary,
            environment_state_summary=f"Time: {datetime.utcnow().isoformat()}",
            potential_intent="User instruction execution"
        )

def run_aios_task(
    run_id: str,
    artifact_base_dir: Path,
    user_instruction: str,
    llm_api_key: str,
    max_steps: int = 20,
):
    print(f"\n--- Starting AIOS Task: {run_id} ---")
    
    run_artifact_dir = artifact_base_dir / run_id
    run_artifact_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = run_artifact_dir / "events.jsonl"
    graph_file_path = run_artifact_dir / "graph_memory.json"
    artifacts_path = run_artifact_dir / "artifacts"
    artifacts_path.mkdir(exist_ok=True)

    if not llm_api_key:
        print("ERROR: LLM API Key is missing.")
        return TaskResult(status="failed", final_summary="LLM API Key missing.", artifacts_dir=str(run_artifact_dir))

    try:
        print("\nStep 1: Initializing AIOS components...")
        event_stream = JsonlLogger(log_file_path)
        graph_memory = GraphMemory(graph_file_path)
        llm_client = LLMClient(api_key=llm_api_key)
        observer = DemoObserver(artifacts_path=artifacts_path)
        
        # The protocol and actuator are now combined into a single logical unit for the demo
        protocol_and_actuator = SimpleNamespace(
            verify_and_execute=combined_protocol_and_actuator
        )

        completion_judge = CompletionJudge(
            goal=user_instruction,
            rule_based_checklist_config={}
        )

        print("\nStep 2: Initializing TaskLoopController...")
        
        # We need to adapt the TaskLoopController to this new combined interface
        # For now, let's create a wrapper that fits the old model
        class ProtocolWrapper:
            def verify_action_plan(self, ap: ActionPlan) -> VerifiedActionPlan:
                return process_action_plan(ap)
        
        class ActuatorWrapper:
            def execute_action(self, vp: VerifiedActionPlan):
                return real_execute_action(vp)

        task_controller = TaskLoopController(
            user_instruction=user_instruction,
            max_steps=max_steps,
            artifacts_dir=run_artifact_dir,
            llm_client=llm_client,
            observer=observer,
            action_protocol=ProtocolWrapper(),
            actuator=ActuatorWrapper(),
            event_stream=event_stream,
            graph_memory=graph_memory,
            completion_judge=completion_judge
        )
        
        task_result = task_controller.run()
        
        print(f"\n--- AIOS Task: {run_id} Completed ---")
        print(f"Task Result: {task_result.status}")
        print(f"Final Summary: {task_result.final_summary}")
        
        graph_memory.save()
        
        return task_result

    except Exception as e:
        print(f"AIOS Task {run_id} failed unexpectedly: {e}")
        import traceback
        traceback.print_exc()
        return TaskResult(status="failed", final_summary=f"Unexpected error: {e}", artifacts_dir=str(run_artifact_dir))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AIOS Demo Task.")
    parser.add_argument("--user_instruction", type=str, default="Open Notepad, create new file, type Hello AIOS", help="User instruction.")
    parser.add_argument("--llm_api_key", type=str, default=os.environ.get("OPENAI_API_KEY"), help="LLM API Key.")
    parser.add_argument("--max_steps", type=int, default=20, help="Maximum execution steps.")
    args = parser.parse_args()

    demo_run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_artifact_dir = Path("./aios_demo_runs")
    print("--- Preparing AIOS Demo ---")
    print(f"Artifacts will be stored in: {base_artifact_dir / demo_run_id}")
    print("Starting in 5 seconds...")
    time.sleep(5)
    
    final_task_result = run_aios_task(
        run_id=demo_run_id,
        artifact_base_dir=base_artifact_dir,
        user_instruction=args.user_instruction,
        llm_api_key=args.llm_api_key,
        max_steps=args.max_steps
    )
    print("\nAIOS Demo Finished.")
    print(f"Final Task Status: {final_task_result.status}")
    print(f"Check logs and artifacts in {final_task_result.artifacts_dir}")
