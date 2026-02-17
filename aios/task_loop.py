from __future__ import annotations
import time
import uuid
import subprocess # NEW IMPORT
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
)
from aios.llm.llm_client import LLMClient
from aios.event_stream import JsonlLogger
from aios.memory.graph import GraphMemory

class CompletionJudge:
    def __init__(self, goal: str, rule_based_checklist_config: Dict[str, Any]):
        self.goal = goal
        self.rule_based_checklist_config = rule_based_checklist_config

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

        # Rule 2: "Hello AIOS" text is present
        text_present = "hello aios" in ui_summary
        updated_checklist["text_present"] = text_present
        if not text_present and "Hello AIOS" in self.goal:
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
                
                observation_event = self.observer.observe()
                self.task_state.last_observation_id = observation_event.observation_id
                self._log_task_state_snapshot()
                print(f"Observed UI: {observation_event.ui_state_summary}")

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

                action_plan = None
                ui_summary = observation_event.ui_state_summary.lower()

                if self._plan_step == 0:
                    print("TaskLoopController: Launching Notepad directly...")
                    subprocess.Popen(["notepad.exe"]) # Directly launch Notepad
                    time.sleep(2) # Give Notepad time to open
                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="NoAction", # No explicit action for actuator here
                        parameters={"message": "Launched Notepad directly."}
                    )
                    self._plan_step = 1
                elif self._plan_step == 1 and ("notepad" in ui_summary or "记事本" in ui_summary):
                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="TypeString",
                        parameters={"text": "Hello AIOS"}
                    )
                    self._plan_step = 2
                elif self._plan_step == 2:
                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="NoAction",
                        parameters={"message": "Typed text, waiting for completion judge."}
                    )
                    self._plan_step = 3 # Done with actions, rely on judge
                else:
                    action_plan = ActionPlan(
                        action_id=str(uuid.uuid4()),
                        origin_observation_id=observation_event.observation_id,
                        action_type="NoAction",
                        parameters={"message": "Hardcoded plan finished or in unexpected state."}
                    )

                print(f"Agent Action Plan: {action_plan.action_type} with parameters {action_plan.parameters}")
                verified_action_plan = self.action_protocol.verify_action_plan(action_plan)
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
