from __future__ import annotations
import time
import uuid
import subprocess
import win32gui
import re
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
    NoActionParameters,
    KeyPressParameters,
    TypeStringParameters
)
from aios.llm.llm_client import LLMClient
from aios.event_stream import JsonlLogger
from aios.memory.graph import GraphMemory
from aios.utils.window_manager import get_notepad_window_info, ensure_foreground_window, is_foreground # NEW IMPORT
from aios.utils.clipboard_manager import get_clipboard_text, clear_clipboard
from aios.planner.task_decomposer import TaskDecomposer
from aios.planner.next_action_planner import NextActionPlanner
from aios.evaluator.subgoal_evaluator import SubgoalEvaluator # NEW IMPORT for Module 4

class CompletionJudge:
    def __init__(self, goal: str, rule_based_checklist_config: Dict[str, Any]):
        self.goal = goal
        self.rule_based_checklist_config = rule_based_checklist_config
        self.expected_text = ""
        print(f"CompletionJudge: Initialized, expected text will be set by controller.")

    def judge(self, task_state: TaskState, observation: ObservationEvent) -> Dict[str, Any]:
        updated_checklist = task_state.checklist.copy()
        is_done = False
        missing_keys = []
        
        ui_summary = observation.ui_state_summary.lower()
        
        notepad_opened = "notepad" in ui_summary or "记事本" in ui_summary
        updated_checklist["notepad_opened"] = notepad_opened
        if not notepad_opened:
            missing_keys.append("notepad_opened")

        text_present = task_state.checklist.get("text_present", False)
        updated_checklist["text_present"] = text_present
        
        if not text_present and task_state.expected_typed_text:
            missing_keys.append("text_present")

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
        
        # --- Dynamic Text Extraction ---
        # Try to find "type in X", "type X", or "输入 X"
        match_type_in = re.search(r'(?:type in|输入)\s+([^,，\n]+)', user_instruction, re.IGNORECASE)
        match_type = re.search(r'(?:type)\s+([^,，\n]+)', user_instruction, re.IGNORECASE)

        if match_type_in:
            expected_text = match_type_in.group(1).strip()
        elif match_type:
            expected_text = match_type.group(1).strip()
        elif "打个招呼" in user_instruction:
            expected_text = "Hello" # Fallback for this specific phrase
        else:
            expected_text = "Hello AIOS" # Default fallback
        self.task_state = TaskState(
            goal=user_instruction, 
            max_steps=max_steps,
            expected_typed_text=expected_text,
            current_subgoal_index=0
        )
        print(f"TaskLoopController: Expected typed text: '{self.task_state.expected_typed_text}'")
        
        self.completion_judge.expected_text = self.task_state.expected_typed_text.lower()

        self.task_decomposer = TaskDecomposer(
            llm_client=self.llm_client,
            prompt_path=Path(__file__).parent.parent / "aios" / "prompts" / "task_decomposer.md"
        )
        
        self.next_action_planner = NextActionPlanner(
            llm_client=self.llm_client,
            prompt_path=Path(__file__).parent.parent / "aios" / "prompts" / "next_action_planner.md"
        )

        self.subgoal_evaluator = SubgoalEvaluator(expected_typed_text=self.task_state.expected_typed_text)
        
        # self._plan_step is no longer needed with LLM planning
        # self._plan_step = 0


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
        if first_action.get("action_type") in ["KeyPress", "Log"] and \
           first_action.get("parameters", {}).get("key") in ["a", "c"] and \
           self.task_state.verify_attempts < 2:
           return False

        for i in range(1, self.task_state.stuck_threshold):
            if first_action.get("action_type") != self.task_state.last_actions[i].get("action_type") or \
               first_action.get("parameters") != self.task_state.last_actions[i].get("parameters"):
                return False
        return True

    def run(self) -> TaskResult:
        print(f"TaskLoopController: Starting task '{self.user_instruction}' for {self.max_steps} steps.")
        try:
            if not self.task_state.subgoals:
                print("TaskLoopController: Decomposing goal into subgoals...")
                constraints = {"non_destructive": True, "no_secret_typing": True}
                decomposed_subgoals = self.task_decomposer.decompose_goal(
                    user_goal=self.user_instruction,
                    constraints=constraints
                )
                self.task_state.subgoals = decomposed_subgoals
                print(f"TaskLoopController: Decomposed subgoals: {self.task_state.subgoals}")
                
            for i in range(self.max_steps):
                self.task_state.step_index = i
                print(f"--- Step {i+1}/{self.max_steps} ---")
                
                observation_event = self.observer.observe()
                self.task_state.last_observation_id = observation_event.observation_id
                self._log_task_state_snapshot()
                print(f"Observed UI: {observation_event.ui_state_summary}")

                # --- Completion Judge Phase ---
                judge_results = self.completion_judge.judge(self.task_state, observation_event)
                self.task_state.checklist.update(judge_results["updated_checklist"])
                print(f"Current Checklist: {self.task_state.checklist}")
                
                # --- Subgoal Advancement Logic (using SubgoalEvaluator) ---
                if self.task_state.subgoals and self.task_state.current_subgoal_index < len(self.task_state.subgoals):
                    current_subgoal = self.task_state.subgoals[self.task_state.current_subgoal_index]
                    
                    # Need readback_text for evaluator, so perform clipboard read here if text_present is not yet true
                    readback_text = ""
                    if not self.task_state.checklist.get("text_present", False):
                        # This section is copied from the old hardcoded plan step 2.1
                        # This is a temporary measure until NextActionPlanner learns to do this
                        # or until SubgoalEvaluator requests it.
                        if self.task_state.target_hwnd:
                            ensure_foreground_window(self.task_state.target_hwnd)
                            time.sleep(0.1)
                        # Send Ctrl+A
                        verified_action_plan_a = self.action_protocol.verify_action_plan(
                            ActionPlan(action_id=str(uuid.uuid4()), origin_observation_id=observation_event.observation_id, action_type="KeyPress", parameters={"key": "a", "modifiers": ["ctrl"]}))
                        self.actuator.execute_action(verified_action_plan_a)
                        self._update_task_state_from_action(verified_action_plan_a.action_plan)
                        time.sleep(1) # Allow time for selection
                        # Send Ctrl+C
                        clear_clipboard() # Clear before copy
                        verified_action_plan_c = self.action_protocol.verify_action_plan(
                            ActionPlan(action_id=str(uuid.uuid4()), origin_observation_id=observation_event.observation_id, action_type="KeyPress", parameters={"key": "c", "modifiers": ["ctrl"]}))
                        self.actuator.execute_action(verified_action_plan_c)
                        self._update_task_state_from_action(verified_action_plan_c.action_plan)
                        time.sleep(1) # Allow time for copy
                        readback_text = get_clipboard_text() or ""
                        print(f"TaskLoopController: Pre-evaluator clipboard readback: '{readback_text}'")
                        if self.task_state.expected_typed_text and self.task_state.expected_typed_text.lower() in readback_text.lower():
                            self.task_state.checklist["text_present"] = True
                            judge_results["updated_checklist"]["text_present"] = True # Update for evaluator
                        # End of temporary clipboard read

                    is_current_subgoal_done = self.subgoal_evaluator.is_done(
                        subgoal_id=current_subgoal["id"],
                        checklist=judge_results["updated_checklist"], # Use updated checklist
                        ui_summary=observation_event.ui_state_summary,
                        readback_text=readback_text, # Pass actual readback text
                        target_hwnd=self.task_state.target_hwnd # Pass target_hwnd for focus checks
                    )

                    if is_current_subgoal_done:
                        print(f"SubgoalEvaluator: Subgoal '{current_subgoal['id']}' achieved. Advancing subgoal index.")
                        self.task_state.current_subgoal_index += 1
                        # Reset recovery counters for next subgoal
                        self.task_state.verify_attempts = 0
                        self.task_state.retype_attempts = 0
                        # Ensure index doesn't go out of bounds
                        if self.task_state.current_subgoal_index >= len(self.task_state.subgoals):
                            self.task_state.current_subgoal_index = len(self.task_state.subgoals) - 1
                # --- END SUBGOAL ADVANCEMENT LOGIC ---

                if judge_results["is_done"]:
                    self._log_task_state_snapshot()
                    print(f"Task completed successfully in {i+1} steps.")
                    return TaskResult(
                        status="success",
                        final_summary=f"Task '{self.user_instruction}' completed successfully.",
                        artifacts_dir=str(self.artifacts_dir)
                    )

                # --- NextActionPlanner Integration ---
                input_bundle = {
                    "goal": self.user_instruction,
                    "current_subgoal_id": self.task_state.subgoals[self.task_state.current_subgoal_index].get("id") if self.task_state.subgoals else None,
                    "subgoals": self.task_state.subgoals,
                    "checklist": self.task_state.checklist,
                    "ui_summary": observation_event.ui_state_summary,
                    "target_hwnd": self.task_state.target_hwnd,
                    "target_pid": self.task_state.target_pid,
                    "recent_actions": self.task_state.last_actions,
                    "recovery_counters": {
                        "verify_attempts": self.task_state.verify_attempts,
                        "retype_attempts": self.task_state.retype_attempts,
                    },
                }
                
                planned_action_dict = self.next_action_planner.plan_next_action(input_bundle)

                parameter_map = {
                    "KeyPress": KeyPressParameters,
                    "TypeString": TypeStringParameters,
                    "MouseClick": MouseClickParameters,
                    "Log": LogParameters,
                    "NoAction": NoActionParameters,
                }
                
                action_parameters = None
                if planned_action_dict["action_type"] in parameter_map:
                    action_parameters = parameter_map[planned_action_dict["action_type"]](**planned_action_dict["parameters"])
                else:
                    action_parameters = NoActionParameters(message=f"Unknown action type from planner: {planned_action_dict['action_type']}")

                action_plan = ActionPlan(
                    action_id=str(uuid.uuid4()),
                    origin_observation_id=observation_event.observation_id,
                    action_type=planned_action_dict["action_type"],
                    parameters=action_parameters
                )

                print(f"Agent Action Plan: {action_plan.action_type} with parameters {action_plan.parameters}")
                verified_action_plan = self.action_protocol.verify_action_plan(action_plan)
                
                # --- Safety Gate Handling ---
                if verified_action_plan.status == "rejected_unsafe":
                    print(f"Safety Gate Rejected Action: {verified_action_plan.validation_messages}")
                    # Log the rejection, maybe increment a counter, and continue to next step
                    # For now, we'll log and let the planner try again
                    self._update_task_state_from_action(ActionPlan(
                        action_id=str(uuid.uuid4()), 
                        origin_observation_id=observation_event.observation_id,
                        action_type="Log",
                        parameters=LogParameters(message=f"Safety rejected: {', '.join(verified_action_plan.validation_messages)}")
                    ))
                    # Do not execute the unsafe action; loop to next step for replanning
                    continue
                # --- End Safety Gate Handling ---

                receipt = self.actuator.execute_action(verified_action_plan)
                print(f"Actuator Receipt: Status='{receipt.status}', Message='{receipt.message}'")
                
                self._update_task_state_from_action(verified_action_plan.action_plan)
                self._log_task_state_snapshot()

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
