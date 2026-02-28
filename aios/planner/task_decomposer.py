import json
import re
from pathlib import Path
from typing import Any, Dict, List
from string import Template # NEW IMPORT

from aios.llm.llm_client import LLMClient
from pydantic import ValidationError, BaseModel, Field

class Subgoal(BaseModel):
    id: str = Field(..., description="Unique ID for the subgoal (snake_case).")
    done_when: str = Field(..., description="Observable condition for when this subgoal is considered done.")

class TaskDecomposerOutput(BaseModel):
    subgoals: List[Subgoal] = Field(..., min_length=3, max_length=8, description="A list of 3-8 distinct, sequential subgoals.")
    notes: str = Field("", description="Short, high-level overview of the decomposition rationale.")

class TaskDecomposer:
    def __init__(self, llm_client: LLMClient, prompt_path: Path):
        self.llm_client = llm_client
        self.prompt_path = prompt_path
        self.system_prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> Template: # Changed return type
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return Template(f.read()) # Wrap in Template

    def decompose_goal(self, user_goal: str, constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        # The prompt template *is* the user prompt, with system instructions embedded.
        user_prompt = self.system_prompt_template.substitute( # Changed .format to .substitute
            user_goal=user_goal,
            constraints=json.dumps(constraints, indent=2)
        )
        
        print("\n--- Calling Task Decomposer LLM ---")
        print(f"Prompt:\n{user_prompt[:500]}...") # Print first 500 chars of prompt
        
        # LLMClient.generate expects system_prompt, user_prompt, json_schema
        # In this case, the full prompt for the LLM is embedded in `user_prompt`
        # and there's no separate "system" prompt from the perspective of the LLMClient's API.
        # We will use an empty system prompt and put the full template into user_prompt.
        llm_response = self.llm_client.generate(
            system_prompt="You are an expert AI agent designed to decompose a user's high-level goal into a sequence of observable subgoals. Your output MUST be a strict JSON object.",
            user_prompt=user_prompt,
            json_schema=TaskDecomposerOutput.model_json_schema() # Pass the schema for strict JSON mode
        )
        
        raw_llm_output = llm_response.get("text") # Extract text if not parsed directly
        if isinstance(llm_response, dict) and llm_response.get("subgoals"): # If LLM client directly returned parsed JSON
             # This means LLMClient.generate successfully parsed JSON
             # But it doesn't return the full TaskDecomposerOutput, just the raw dict from LLM
             # So we re-validate it against our model to ensure types are correct
             try:
                validated_output = TaskDecomposerOutput.model_validate(llm_response)
                print(f"Parsed LLM Output (from direct JSON response): {llm_response.get('subgoals')[:500]}...")
                return [sg.model_dump() for sg in validated_output.subgoals]
             except ValidationError as e:
                print(f"TaskDecomposer: LLMClient returned JSON but validation failed: {e}")
                raw_llm_output = json.dumps(llm_response) # Fallback to raw string for manual parsing attempt

        # Fallback to manual JSON extraction and parsing if LLMClient.generate didn't return parsed JSON directly
        print(f"Raw LLM Output (after LLMClient.generate):\n{raw_llm_output[:500]}...")

        try:
            json_match = re.search(r"```json\n({.*?})\n```", raw_llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = raw_llm_output

            parsed_output = json.loads(json_str)
            validated_output = TaskDecomposerOutput.model_validate(parsed_output)
            return [sg.model_dump() for sg in validated_output.subgoals]
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"TaskDecomposer: Failed to parse/validate LLM output manually: {e}")
            print(f"Raw LLM Output that failed manual parsing: {raw_llm_output}")
            print("TaskDecomposer: Falling back to default Notepad decomposition.")
            return [
                {"id": "open_notepad", "done_when": "notepad window exists and is foreground"},
                {"id": "new_file", "done_when": "a fresh editable document is active"},
                {"id": "type_text", "done_when": "clipboard readback contains the expected text"},
                {"id": "close_notepad", "done_when": "notepad window does not exist"}
            ]
        except Exception as e:
            print(f"TaskDecomposer: An unexpected error occurred during manual parsing: {e}")
            return [
                {"id": "open_notepad", "done_when": "notepad window exists and is foreground"},
                {"id": "new_file", "done_when": "a fresh editable document is active"},
                {"id": "type_text", "done_when": "clipboard readback contains the expected text"},
                {"id": "close_notepad", "done_when": "notepad window does not exist"}
            ]
