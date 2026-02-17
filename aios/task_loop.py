from __future__ import annotations
import time
import uuid
import subprocess
import win32gui
import re # NEW IMPORT for parsing user_instruction
from typing import Any, Dict, List, Literal, Optional, Union
from datetime import datetime
from pathlib import Path

from pydantic import Field, BaseModel

from aios.protocols.schema import (
    AIOSBaseModel,
    ActionPlan,
    Receipt,
    ObservationEvent,
    EventType,
    Event,
    TaskState,
    TaskResult,
    MouseClickParameters,
    LogParameters,
    NoActionParameters # NEW IMPORT
)
from aios.llm.llm_client import LLMClient
from aios.event_stream import JsonlLogger
from aios.memory.graph import GraphMemory
from aios.utils.window_manager import get_notepad_window_info, ensure_foreground_window
from aios.utils.clipboard_manager import get_clipboard_text, clear_clipboard

class CompletionJudge:
    def __init__(self, goal: str, rule_based_checklist_config: Dict[str, Any]):
        self.goal = goal
        self.rule_based_checklist_config = rule_based_checklist_config
        # Extract expected text from goal if present
        match = re.search(r'(?:输入|type)\s+(.*?)(?:\n|$)', goal, re.IGNORECASE)
        self.expected_text = (match.group(1).strip() if match else "Hello AIOS").lower()
        print(f"CompletionJudge: Expected text derived from goal: '{self.expected_text}'")

    def judge(self, task_state: TaskState, observation: ObservationEvent) -> Dict[str, Any]:
        updated_checklist = task_state.checklist.copy()
        is_done = False
        missing_keys = []
        
        ui_summary = observation.ui_state_summary.lower()
        
        # Rule 1: Notepad is open
        notepad_opened = "notepad" in ui_summary or "记事本" in ui_summary
        updated_checklist["notepad_opened"] = notepad_opened
        if not notepad_opened:
            missing_keys.append("notepad_opened")

        # Rule 2: Expected text is present (from clipboard readback via TaskLoopController)
        text_present = task_state.checklist.get("text_present", False)
        updated_checklist["text_present"] = text_present
        if not text_present and self.expected_text:
            missing_keys.append("text_present")

        # Completion Condition
        if updated_checklist.get("notepad_opened") and updated_checklist.get("text_present"):
            is_done = True
        
        return {"updated_checklist": updated_checklist, "is_done": is_done, "missing_keys": missing_keys}


class TaskLoopController:
    def __init__(
        self,
        user_instruction: str,
        max_steps: int,
        artifacts_dir: Path,
        llm_client: LLMClient,
        observer: Any,
        action_protocol: Any,
        actuator: Any,
        event_stream: JsonlLogger,
        graph_memory: GraphMemory,
        completion_judge: CompletionJudge,
    ):
        self.user_instruction = user_instruction
        self.max_steps = max_steps
        self.llm_client = llm_client
        self.observer = observer
        self.action_protocol = action_protocol
        self.actuator = actuator
        self.event_stream = event_stream
        self.graph_memory = graph_memory
        self.completion_judge = completion_judge
        self.artifacts_dir = artifacts_dir
        self.task_state = TaskState(goal=user_instruction, max_steps=max_steps)
        # Extract expected text from user_instruction
        match = re.search(r'(?:输入|type)\s+(.*?)(?:\n|$)', user_instruction, re.IGNORECASE)
        self.expected_typed_text = match.group(1).strip() if match else "Hello AIOS"
        print(f"TaskLoopController: Expected typed text: '{self.expected_typed_text}'")

        # Add internal state for hardcoded plan
        self._plan_step = 0

    def _log_task_state_snapshot(self):
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.TASK_STATE_SNAPSHOT,
            payload=self.task_state.model_copy(deep=True)
        )
        self.event_stream.log_event(event)
        self.graph_memory.update(event)

    def _update_task_state_from_action(self, action_plan: ActionPlan):
        self.task_state.last_actions.append({
            "action_type": action_plan.action_type,
            "parameters": action_plan.parameters.model_dump(),
            "timestamp": datetime.utcnow().isoformat()
        })
        if len(self.task_state.last_actions) > self.task_state.stuck_threshold:
            self.task_state.last_actions.pop(0)

    def _check_stuck_loop(self) -> bool:
        if len(self.task_state.last_actions) < self.task_state.stuck_threshold:
            return False
        
        first_action = self.task_state.last_actions[0]
        # Allow repeated clipboard actions for verification to not trigger stuck loop
        if first_action.get("action_type") in ["KeyPress", "Log"] and \
           first_action.get("parameters", {}).get("key") in ["a", "c"] and \
           self.task_state.verify_attempts < 2: # Allow some retries before flagging as stuck
           return False

        for i in range(1, self.task_state.stuck_threshold):
            if first_action.get("action_type") != self.task_state.last_actions[i].get("action_type") or \
               first_action.get("parameters") != self.task_state.last_actions[i].get("parameters"):
                return False
        return True

    def run(self) -> TaskResult:
        print(f"TaskLoopController: Starting task '{self.user_instruction}' for {self.max_steps} steps.")
        try:
            for i in range(self.max_steps):
                self.task_state.step_index = i
                print(f"--- Step {i+1}/{self.max_steps} ---")
                
                # --- Observation Phase ---
                observation_event = self.observer.observe()
                self.task_state.last_observation_id = observation_event.observation_id
                self._log_task_state_snapshot()
                print(f"Observed UI: {observation_event.ui_state_summary}")

                # --- Decision & Action Phase ---
                action_plan = None
                ui_summary = observation_event.ui_state_summary.lower()

                # Ensure Notepad is foreground before any actions if we have a target
                if self.task_state.target_hwnd:
                    ensure_foreground_window(self.task_state.target_hwnd)
                    time.sleep(0.5) # Give some time for focus to shift

                if self._plan_step == 0:
                    print("TaskLoopController: Launching Notepad directly...")
                    subprocess.Popen(["notepad.exe"])
                    time.sleep(2) # Give Notepad time to open
                    hwnd, pid = get_notepad_window_info()
                    if hwnd and pid:
                        self.task_state.target_hwnd = hwnd
                        self.task_state.target_pid = pid
                        print(f"TaskLoopController: Targeted Notepad HWND: {hwnd}, PID: {pid}")
                    else:
                        print("TaskLoopController: Warning: Could not find Notepad window after launch.")

                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="NoAction",
                        parameters=NoActionParameters(message="Launched Notepad directly.")
                    )
                    self._plan_step = 1
                elif self._plan_step == 1 and ("notepad" in ui_summary or "记事本" in ui_summary):
                    # Ensure a new document before typing
                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="KeyPress",
                        parameters={"key": "n", "modifiers": ["ctrl"]} # Ctrl+N for new document
                    )
                    self._plan_step = 1.5 # Intermediate step for new file handling
                elif self._plan_step == 1.5:
                    # Check for "Save changes to Untitled?" dialog.
                    # This requires observer to be able to detect specific dialogs
                    if "save changes to untitled" in ui_summary or "是否将更改保存到" in ui_summary: # Localized string for Notepad Save dialog
                        print("TaskLoopController: Save dialog detected. Sending Alt+N to 'Don't Save'.")
                        action_plan = ActionPlan(
                            action_id=str(uuid.uuid4()),
                            origin_observation_id=observation_event.observation_id,
                            action_type="KeyPress",
                            parameters={"key": "n", "modifiers": ["alt"]} # Alt+N for Don't Save
                        )
                        self._plan_step = 1.6 # Give it a moment to dismiss
                    else: # No save dialog or already dismissed, proceed to typing
                        action_plan = ActionPlan(
                            action_id=str(uuid.uuid4()),
                            origin_observation_id=observation_event.observation_id,
                            action_type="Log",
                            parameters=LogParameters(message="New document ready or no save dialog.")
                        )
                        self._plan_step = 2 # Proceed to typing
                elif self._plan_step == 1.6: # After Alt+N, proceed to typing
                     action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="Log",
                        parameters=LogParameters(message="Save dialog dismissed. Proceeding to typing.")
                    )
                     self._plan_step = 2 # Proceed to typing
                elif self._plan_step == 2:
                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="TypeString",
                        parameters={"text": self.expected_typed_text} # DYNAMIC TEXT
                    )
                    self._plan_step = 2.1 # Proceed to clipboard readback
                elif self._plan_step == 2.1: # After typing, now perform clipboard readback and recovery
                    clipboard_content = ""
                    # Retry clipboard verification up to a limit
                    if self.task_state.verify_attempts < 3: # Max 3 attempts
                        # Ensure Notepad is foreground before Ctrl+A/C
                        if self.task_state.target_hwnd:
                            ensure_foreground_window(self.task_state.target_hwnd)
                            time.sleep(0.1)

                        # Send Ctrl+A
                        verified_action_plan_a = self.action_protocol.verify_action_plan(
                            ActionPlan(
                                action_id=str(uuid.uuid4()),
                                origin_observation_id=observation_event.observation_id,
                                action_type="KeyPress",
                                parameters={"key": "a", "modifiers": ["ctrl"]}
                            )
                        )
                        self.actuator.execute_action(verified_action_plan_a)
                        self._update_task_state_from_action(verified_action_plan_a.action_plan)
                        time.sleep(1) # Allow time for selection

                        # Send Ctrl+C
                        clear_clipboard() # Clear before copy
                        verified_action_plan_c = self.action_protocol.verify_action_plan(
                            ActionPlan(
                                action_id=str(uuid.uuid4()),
                                origin_observation_id=observation_event.observation_id,
                                action_type="KeyPress",
                                parameters={"key": "c", "modifiers": ["ctrl"]}
                            )
                        )
                        self.actuator.execute_action(verified_action_plan_c)
                        self._update_task_state_from_action(verified_action_plan_c.action_plan)
                        time.sleep(1) # Allow time for copy

                        clipboard_content = get_clipboard_text()
                        print(f"TaskLoopController: Clipboard content for verification: '{clipboard_content}' (Attempt {self.task_state.verify_attempts + 1})")

                        normalized_clipboard_content = (clipboard_content or "").strip().replace('\r\n', '\n').lower()
                        if self.expected_typed_text.lower() in normalized_clipboard_content: # DYNAMIC VERIFICATION
                            self.task_state.checklist["text_present"] = True
                            self.task_state.verify_attempts = 0 # Reset attempts on success
                            self.task_state.retype_attempts = 0 # Reset retype attempts
                            action_plan = ActionPlan(
                                action_id=str(uuid.uuid4()),
                                origin_observation_id=observation_event.observation_id,
                                action_type="Log",
                                parameters=LogParameters(message="Text verified via clipboard.")
                            )
                            self._plan_step = 3 # Text verified, next check completion
                        else:
                            self.task_state.verify_attempts += 1
                            if self.task_state.retype_attempts < 1: # Only 1 retype attempt
                                # Recovery: click in editor and re-type
                                print("TaskLoopController: Clipboard verification failed. Retrying typing.")
                                if self.task_state.target_hwnd:
                                    rect = win32gui.GetWindowRect(self.task_state.target_hwnd)
                                    center_x = (rect[0] + rect[2]) // 2
                                    center_y = (rect[1] + rect[3]) // 2
                                else:
                                    center_x, center_y = 500, 300 # Fallback arbitrary screen center
                                
                                # Send MouseClick
                                verified_action_plan_click = self.action_protocol.verify_action_plan(
                                    ActionPlan(
                                        action_id=str(uuid.uuid4()),
                                        origin_observation_id=observation_event.observation_id,
                                        action_type="MouseClick",
                                        parameters=MouseClickParameters(x=center_x, y=center_y).model_dump()
                                    )
                                )
                                self.actuator.execute_action(verified_action_plan_click)
                                self._update_task_state_from_action(verified_action_plan_click.action_plan)
                                time.sleep(0.5)

                                # Re-type
                                action_plan = ActionPlan(
                                    action_id=str(uuid.uuid4()),
                                    origin_observation_id=observation_event.observation_id,
                                    action_type="TypeString",
                                    parameters={"text": self.expected_typed_text} # DYNAMIC TEXT
                                )
                                self.task_state.retype_attempts += 1
                                # Keep _plan_step at 2 to re-attempt verification next cycle
                            else:
                                # Retries exhausted, fail the task
                                print("TaskLoopController: Clipboard verification failed after retries. Failing task.")
                                return TaskResult(
                                    status="failed",
                                    final_summary="Text verification failed after retries.",
                                    artifacts_dir=str(self.artifacts_dir)
                                )
                    else: # verify_attempts exhausted
                        print("TaskLoopController: Clipboard verification attempts exhausted. Failing task.")
                        return TaskResult(
                            status="failed",
                            final_summary="Text verification attempts exhausted.",
                            artifacts_dir=str(self.artifacts_dir)
                        )
                else: # Default NoAction if plan_step is not recognized or already completed
                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="NoAction",
                        parameters=NoActionParameters(message="Hardcoded plan finished or in unexpected state.")
                    )

                print(f"Agent Action Plan: {action_plan.action_type} with parameters {action_plan.parameters}")
                verified_action_plan = self.action_protocol.verify_action_plan(action_plan)
                receipt = self.actuator.execute_action(verified_action_plan)
                print(f"Actuator Receipt: Status='{receipt.status}', Message='{receipt.message}'")
                
                self._update_task_state_from_action(verified_action_plan.action_plan)
                self._log_task_state_snapshot()

                # --- Completion Judge Phase ---
                judge_results = self.completion_judge.judge(self.task_state, observation_event)
                self.task_state.checklist.update(judge_results["updated_checklist"])
                print(f"Current Checklist: {self.task_state.checklist}")
                
                if judge_results["is_done"]:
                    self._log_task_state_snapshot()
                    print(f"Task completed successfully in {i+1} steps.")
                    return TaskResult(
                        status="success",
                        final_summary=f"Task '{self.user_instruction}' completed successfully.",
                        artifacts_dir=str(self.artifacts_dir)
                    )

                if self._check_stuck_loop():
                    self._log_task_state_snapshot()
                    print("Task terminated: Stuck loop detected.")
                    return TaskResult(status="stuck_loop_detected", final_summary="Task terminated due to repeated actions.", artifacts_dir=str(self.artifacts_dir))

            self._log_task_state_snapshot()
            print(f"Task terminated: Max steps ({self.max_steps}) exceeded.")
            return TaskResult(status="max_steps_exceeded", final_summary="Task could not be completed within max steps.", artifacts_dir=str(self.artifacts_dir))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"TaskLoopController: Task '{self.user_instruction}' failed unexpectedly: {e}")
            self._log_task_state_snapshot()
            return TaskResult(status="failed", final_summary=f"Unexpected error: {e}", artifacts_dir=str(self.artifacts_dir))
