from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

from aios.protocols.schema import ObservationEvent

class GraphMemory:
    """
    A simple dictionary-based graph memory, serialized to a JSON file.

    This is a minimal implementation for the demo, prioritizing simplicity
    and replayability over performance with large graphs.
    """

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Loads the graph from the specified file path if it exists."""
        if self.file_path.exists():
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.nodes = data.get("nodes", {})
                self.edges = data.get("edges", [])
            print(f"GraphMemory loaded from {self.file_path}")
        else:
            print(f"No existing graph file found at {self.file_path}. Starting fresh.")

    def save(self):
        """Saves the current graph state to the file path."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump({"nodes": self.nodes, "edges": self.edges}, f, indent=4)
        print(f"GraphMemory saved to {self.file_path}")

    def update(self, event: ObservationEvent):
        """
        Updates the graph based on a new observation event.

        **Stub Implementation for Iteration 1**:
        This method is a placeholder. For now, it simply creates a single node
        representing the observation event itself to demonstrate the update
        and persistence mechanism.

        Future iterations will implement the logic to create state nodes,
        context nodes, and edges representing transitions, as per architecture.md.
        
        TODO (Iteration 3+):
        1. Implement logic to parse the ObservationEvent.
        2. Create or find existing nodes for the current UI state and environment state.
        3. Create an edge from the previous state node to the current state node,
           labeled with the action that caused the transition (if available).
        """
        node_id = f"observation_{event.observation_id}"
        
        # Avoid duplicating nodes if the event is somehow processed again
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                "type": "ObservationNode",
                "timestamp": event.timestamp.isoformat(),
                "potential_intent": event.potential_intent,
                "ui_summary": event.ui_state_summary,
                "raw_signal_count": len(event.raw_signals),
            }
            print(f"GraphMemory updated: Added node {node_id}")

        # In a real implementation, we would also create edges here to link
        # this observation to previous states or actions.
        # For example: self.edges.append({"from": previous_node, "to": node_id, "type": "TRANSITION"})

    def get_full_graph(self) -> Dict[str, Any]:
        """Returns the entire graph."""
        return {"nodes": self.nodes, "edges": self.edges}
