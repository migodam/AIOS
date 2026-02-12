import json # ADDED
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from aios.protocols.schema import ObservationEvent, GraphUpdate # ADDED GraphUpdate

class GraphMemory:
    """
    A simple memory store for Interaction Graph updates, serialized to a JSON file.
    This iteration focuses on logging GraphUpdate events as part of the graph memory.
    """

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        self.graph_updates: List[GraphUpdate] = [] # Stores sequence of graph updates
        self._previous_observation: Optional[ObservationEvent] = None # For change detection
        self._load()

    def _load(self):
        """Loads the graph updates and previous observation from the specified file path if it exists."""
        if self.file_path.exists():
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.graph_updates = [GraphUpdate.model_validate_json(json.dumps(gu)) for gu in data.get("graph_updates", [])] # Use model_validate_json
                if data.get("previous_observation"):
                    self._previous_observation = ObservationEvent.model_validate_json(json.dumps(data["previous_observation"])) # Use model_validate_json
            print(f"GraphMemory loaded {len(self.graph_updates)} updates from {self.file_path}")
        else:
            print(f"No existing graph memory file found at {self.file_path}. Starting fresh.")

    def save(self):
        """Saves the current graph memory state to the file path."""
        data_to_save = {
            "graph_updates": [json.loads(gu.model_dump_json()) for gu in self.graph_updates], # Use model_dump_json then json.loads
            "previous_observation": json.loads(self._previous_observation.model_dump_json()) if self._previous_observation else None # Use model_dump_json then json.loads
        }
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4)
        print(f"GraphMemory saved {len(self.graph_updates)} updates to {self.file_path}")

    def update(self, observation: ObservationEvent) -> Optional[GraphUpdate]:
        """
        Updates the graph memory based on a new observation event.
        Generates a GraphUpdate if a significant change is detected.
        """
        generated_graph_update: Optional[GraphUpdate] = None
        summary_of_change = ""

        if self._previous_observation is None:
            # First observation, always consider it a change
            summary_of_change = f"Initial observation: Intent '{observation.potential_intent}', UI: '{observation.ui_state_summary}'"
        else:
            # Detect changes in key fields for graph updates
            if observation.potential_intent != self._previous_observation.potential_intent:
                summary_of_change = (f"Intent changed from '{self._previous_observation.potential_intent}' "
                                     f"to '{observation.potential_intent}'. ")
            
            # Simple heuristic for UI summary change - could be more sophisticated (e.g., diffing UIA tree hashes)
            # Only summarize if ui_state_summary is non-empty and has changed
            if observation.ui_state_summary and observation.ui_state_summary != self._previous_observation.ui_state_summary:
                old_summary_short = self._previous_observation.ui_state_summary[:50].replace('\n', ' ') + ('...' if len(self._previous_observation.ui_state_summary) > 50 else '')
                new_summary_short = observation.ui_state_summary[:50].replace('\n', ' ') + ('...' if len(observation.ui_state_summary) > 50 else '')
                summary_of_change += (f"UI summary changed from '{old_summary_short}' "
                                      f"to '{new_summary_short}'.")
            
            if not summary_of_change:
                # No significant change detected
                print(f"GraphMemory: No significant change detected from previous observation {self._previous_observation.observation_id}.")
                self._previous_observation = observation # Still update previous to current
                return None
        
        # If a change was detected, create and store a GraphUpdate
        if summary_of_change:
            generated_graph_update = GraphUpdate(
                observation_id=observation.observation_id,
                summary_of_change=summary_of_change.strip(),
                metadata={"observation_timestamp": observation.timestamp.isoformat()}
            )
            self.graph_updates.append(generated_graph_update)
            print(f"GraphMemory updated: Generated GraphUpdate for observation {observation.observation_id}.")
        
        self._previous_observation = observation
        return generated_graph_update # Return the generated update for logging in the event stream

    def query(self, search_intent: str = "", limit: int = 5) -> List[GraphUpdate]:
        """
        Minimal Query API: Returns recent GraphUpdate objects, optionally filtered by intent.
        For Hierarchical Interaction Graph, this would evolve to more complex pattern matching.
        """
        filtered_updates = []
        for update in reversed(self.graph_updates): # Search most recent first
            if search_intent.lower() in update.summary_of_change.lower():
                filtered_updates.append(update)
            if len(filtered_updates) >= limit:
                break
        return filtered_updates
