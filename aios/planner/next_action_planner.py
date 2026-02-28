import json
import re
from pathlib import Path
from typing import Any, Dict, List, Type
from string import Template

from aios.llm.llm_client import LLMClient
from pydantic import ValidationError, BaseModel, Field

from aios.protocols.schema import ActionPlan, TypeStringParameters, KeyPressParameters, MouseClickParameters, LogParameters, NoActionParameters

# Pydantic model for the NextActionPlanner's output for strong validation
class NextActionPlannerOutput(BaseModel):
    action_type: str = Field(..., description="The type of action to perform.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action.")
    reason: str = Field(..., description="A short explanation for choosing this action.")
    expected_observation: str = Field(..., description="A brief description of the expected UI change or outcome.")
    advance_subgoal: bool = Field(False, description="Set to true if this action completes the current subgoal.")

class NextActionPlanner:
    def __init__(self, llm_client: LLMClient, prompt_path: Path):
        self.llm_client = llm_client
        self.prompt_path = prompt_path
        self.system_prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> Template:
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return Template(f.read())

    def plan_next_action(self, input_bundle: Dict[str, Any]) -> Dict[str, Any]:
        # Prepare available actions schema and examples
        available_actions_schema = self._generate_available_actions_schema()
        
        user_prompt = self.system_prompt_template.substitute(
            goal=input_bundle.get("goal", ""),
            current_subgoal_id=input_bundle.get("current_subgoal_id", "N/A"),
            subgoals=json.dumps(input_bundle.get("subgoals", []), indent=2),
            checklist=json.dumps(input_bundle.get("checklist", {}), indent=2),
            ui_summary=input_bundle.get("ui_summary", "N/A"),
            target_info=json.dumps({"hwnd": input_bundle.get("target_hwnd"), "pid": input_bundle.get("target_pid")}),
            recent_actions=json.dumps(input_bundle.get("recent_actions", []), indent=2),
            recovery_counters=json.dumps(input_bundle.get("recovery_counters", {}), indent=2),
            available_actions_schema=json.dumps(available_actions_schema, indent=2)
        )
        
        print("--- Calling Next-Action Planner LLM ---") # Corrected print statement
        print(f"Prompt:\n{user_prompt[:500]}...") # Corrected print statement

        llm_response = self.llm_client.generate(
            system_prompt="You are an expert AI agent that plans the next executable action. Your output MUST be a strict JSON object.",
            user_prompt=user_prompt,
            json_schema=NextActionPlannerOutput.model_json_schema()
        )
        
        raw_llm_output = llm_response.get("text")
        if isinstance(llm_response, dict) and llm_response.get("action_type"):
            try:
                validated_output = NextActionPlannerOutput.model_validate(llm_response)
                print(f"Parsed LLM Output (from direct JSON response): {llm_response.get('action_type')}...")
                return validated_output.model_dump()
            except ValidationError as e:
                print(f"NextActionPlanner: LLMClient returned JSON but validation failed: {e}")
                raw_llm_output = json.dumps(llm_response)

        print(f"Raw LLM Output (after LLMClient.generate):\n{raw_llm_output[:500]}...") # Corrected print statement

        try:
            json_match = re.search(r"```json\n({.*?})\n```", raw_llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = raw_llm_output

            parsed_output = json.loads(json_str)
            validated_output = NextActionPlannerOutput.model_validate(parsed_output)
            return validated_output.model_dump()
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"NextActionPlanner: Failed to parse/validate LLM output manually: {e}")
            print(f"Raw LLM Output that failed manual parsing: {raw_llm_output}")
            print("NextActionPlanner: Falling back to a NoAction plan.")
            return {
                "action_type": "NoAction",
                "parameters": {"message": f"Planner failed to generate valid JSON: {e}. Raw output: {raw_llm_output[:100]}..."},
                "reason": "LLM output parse error.",
                "expected_observation": "No change.",
                "advance_subgoal": False
            }
        except Exception as e:
            print(f"NextActionPlanner: An unexpected error occurred during manual parsing: {e}")
            return {
                "action_type": "NoAction",
                "parameters": {"message": f"Planner unexpected error: {e}. Raw output: {raw_llm_output[:100]}..."},
                "reason": "Unexpected error during LLM planning.",
                "expected_observation": "No change.",
                "advance_subgoal": False
            }

    def _generate_available_actions_schema(self) -> Dict[str, Any]:
        # Return a simplified schema/examples of actions for the LLM
        return {
            "TypeString": TypeStringParameters.model_json_schema(),
            "KeyPress": KeyPressParameters.model_json_schema(),
            "MouseClick": MouseClickParameters.model_json_schema(),
            "Log": LogParameters.model_json_schema(),
            "NoAction": NoActionParameters.model_json_schema(),
            # Add examples or more detailed descriptions as needed
        }