from __future__ import annotations
from typing import Dict, Any
import uuid

from aios.protocols.schema import ObservationEvent, ActionPlan
from aios.memory.graph import GraphMemory # Agent needs access to graph memory
from aios.protocols.llm_connector import request_core_agent_llm_action

def decide_action(
    observation_event: ObservationEvent,
    graph_memory: GraphMemory,
    user_instruction: str,
    llm_api_key: str,
    core_llm_prompt_filename: str
) -> ActionPlan:
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
    print(f"Agent Orienting: Graph has {len(graph_memory.graph_updates)} recorded updates.")

    # --- Decide: LLM-based Decision Logic ---
    print(f"Agent Decision: Requesting Core Agent LLM for action plan...")
    
    # Get a summary of graph memory for the LLM
    # For now, a very basic summary; will be enhanced in future iterations
    graph_memory_summary = (
        f"Graph contains {len(graph_memory.graph_updates)} recorded updates. "
        f"Most recent observation intent: {observation_event.potential_intent}. "
        f"Most recent UI summary: {observation_event.ui_state_summary}."
    )

    action_plan = request_core_agent_llm_action(
        observation_event=observation_event,
        graph_memory_summary=graph_memory_summary,
        user_instruction=user_instruction,
        llm_api_key=llm_api_key,
        core_llm_prompt_filename=core_llm_prompt_filename
    )
    
    print(f"Agent LLM decided action: {action_plan.action_type}")

    return action_plan

