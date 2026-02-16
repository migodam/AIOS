import json
import dataclasses
from typing import Any, Dict
import re # For desensitize_api_key

def normalize_params(parameters: Any) -> Dict[str, Any]:
    """
    Normalizes a variety of parameter input types into a consistent dictionary.

    Args:
        parameters: Can be None, a dict, a Pydantic v1/v2 model, a dataclass,
                    or another object with __dict__.

    Returns:
        A dictionary representation of the parameters.

    Raises:
        TypeError: If the input object type cannot be normalized.
    """
    if parameters is None:
        return {}
    if isinstance(parameters, dict):
        return parameters
    # Pydantic v2
    if hasattr(parameters, 'model_dump'):
        return parameters.model_dump()
    # Pydantic v1
    if hasattr(parameters, 'dict'):
        return parameters.dict()
    # Dataclass
    if dataclasses.is_dataclass(parameters):
        return dataclasses.asdict(parameters)
    # Generic object (e.g., SimpleNamespace)
    if hasattr(parameters, '__dict__'):
        return parameters.__dict__

    raise TypeError(f"Unsupported parameter type for normalization: {type(parameters)}")

def desensitize_api_key(text: str) -> str:
    """
    Replaces occurrences of 'sk-' followed by alphanumeric characters with 'sk-***'
    to prevent API key leakage.
    """
    if isinstance(text, str):
        # Using a regex to find 'sk-' followed by at least one alphanumeric char
        # and replacing the rest with '*'
        return re.sub(r'(sk-)([a-zA-Z0-9_-]*)', r'\1***', text)
    return text
