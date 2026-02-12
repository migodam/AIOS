from flask import Flask, request, jsonify
from datetime import datetime
import json # ADDED
from aios.protocols.schema import LLMResponseMock # Assuming LLMResponseMock is defined in schema.py

app = Flask(__name__)

@app.route("/", methods=["GET"]) # ADDED FOR READINESS CHECK
def root():
    return "Mock LLM Server is running.", 200

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.json
    user_prompt = ""
    for message in data.get("messages", []):
        if message.get("role") == "user":
            user_prompt = message.get("content", "")
            break

    # Default mock response
    ui_summary = "Desktop is visible."
    environment_summary = "System appears normal."
    potential_intent = "Waiting for user instructions."

    if "play chrome dino" in user_prompt.lower():
        ui_summary = "Google Chrome with Dino game is active."
        potential_intent = "Play Chrome Dino Game."
    elif "notepad" in user_prompt.lower():
        ui_summary = "Notepad window is open and focused."
        potential_intent = "User wants to type in Notepad."
    
    mock_response = LLMResponseMock(
        ui_state_summary=ui_summary,
        environment_state_summary=environment_summary,
        potential_intent=potential_intent
    )

    dumped_data = mock_response.model_dump_json() # Get JSON string from Pydantic
    print("DEBUG: mock_response.model_dump_json() output:", dumped_data) # DEBUG
    return jsonify(json.loads(dumped_data)) # Load JSON string back to dict for jsonify

if __name__ == "__main__":
    print("Starting Mock LLM Server on http://127.0.0.1:8080")
    app.run(host="127.0.0.1", port=8080, debug=False)