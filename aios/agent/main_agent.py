from __future__ import annotations
from typing import Dict, Any
import uuid

from aios.protocols.schema import ObservationEvent, ActionPlan
from aios.memory.graph import GraphMemory # Agent needs access to graph memory

def decide_action(observation_event: ObservationEvent, graph_memory: GraphMemory) -> ActionPlan:
    """
    Agent's decision-making function. Based on the observation and historical
    graph memory, it decides on the next action.

    Args:
        observation_event: The latest structured observation from Protocol1.
        graph_memory: The current state of the Interaction Graph.

    Returns:
        An ActionPlan object.
    """
    action_type = "NoAction"
    parameters: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {"safety_check": True} # Default to safe
    decision_summary = "No specific action decided."

    # --- Orient: Querying Graph Memory (Simplified for Iteration 5) ---
    # For now, we only use graph_memory to show it's accessible.
    # In future iterations, actual querying logic would go here.
    num_nodes = len(graph_memory.nodes)
    num_edges = len(graph_memory.edges)
    print(f"Agent Orienting: Graph has {num_nodes} nodes and {num_edges} edges.")

    # --- Decide: Rule-based Decision Logic (Simplified for Iteration 5) ---
    # Example Rule: If intent is to type in Notepad, then type a string.
    # The LLM connector is mock-configured to set intent to "Preparing to type." if Notepad is open.
    if observation_event.potential_intent == "Preparing to type.":
        action_type = "TypeString"
        # The content to type could be more dynamic, e.g., from LLM, but hardcoded for now.
        parameters["text"] = f"Hello from AIOS! Observed at {observation_event.timestamp.isoformat()}"
        decision_summary = "Typing intent detected. Decided to type a greeting."
    elif observation_event.potential_intent == "Play Chrome Dino Game.": # ADDED DINO LOGIC
        action_type = "KeyPress"
        parameters["key"] = "space"
        parameters["modifiers"] = []
        decision_summary = "Dino game intent detected. Decided to press space to jump."
    elif "System is running the pilot script" in observation_event.environment_state_summary:
        action_type = "Log"
        parameters["message"] = f"AIOS Agent observed pilot script running at {observation_event.timestamp.isoformat()}"
        decision_summary = "Pilot script observed. Decided to log system status."
    
    print(f"Agent Decision: {decision_summary}")

    return ActionPlan(
        action_id=str(uuid.uuid4()),
        origin_observation_id=observation_event.observation_id,
        action_type=action_type,
        parameters=parameters,
        constraints=constraints,
        dry_run=False # Changed to False for actual execution in demo
    )

