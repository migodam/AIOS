from pathlib import Path
from aios.protocols.schema import Event

class JsonlLogger:
    """
    Handles writing AIOS events to an append-only JSONL file.
    """

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        # Ensure the directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"JSONL Logger initialized for file: {self.file_path}")

    def log_event(self, event: Event):
        """
        Serializes an Event model to a JSON string and appends it to the log file.

        Args:
            event: An instance of the Event Pydantic model.
        """
        # `model_dump_json` is the Pydantic v2 method to serialize to a JSON string
        json_string = event.model_dump_json()
        
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json_string + "\n")
        
        print(f"Logged event {event.event_id} of type {event.event_type.value}")

