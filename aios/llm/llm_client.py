import openai
import json
import logging
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception, wait_exponential
import time

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, api_key: str, model_name: str = "gpt-4o", temperature: float = 0.7): # Default to gpt-4o
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.client = openai.OpenAI(api_key=self.api_key)
        logger.info(f"LLMClient initialized with model: {self.model_name}, temperature: {self.temperature}")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception(lambda e: isinstance(e, (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError))), # Catch specific OpenAI errors for retry
        reraise=True
    )
    def generate(self, system_prompt: str, user_prompt: str, json_schema: dict = None) -> dict:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response_format = {}
        if json_schema:
            response_format = {"type": "json_object"}
            # It's good practice to also instruct the LLM in the prompt
            messages[0]["content"] += "\\n\\n" + "You MUST output only a JSON object that strictly adheres to the following schema:"
            messages[0]["content"] += "\\n" + json.dumps(json_schema)


        try:
            time.sleep(0.1) # Small delay to mitigate rate limits
            
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                response_format=response_format if response_format else openai.NOT_SPECIFIED
            )
            
            response_text = completion.choices[0].message.content
            logger.debug(f"Raw LLM response text: {response_text}")
            
            if json_schema:
                parsed_json = json.loads(response_text)
                logger.debug("LLM generated valid JSON and it was parsed.")
                return parsed_json
            else:
                return {"text": response_text}
        except json.JSONDecodeError as e:
            logger.error(f"LLM response not valid JSON: {response_text}. Error: {e}")
            raise ValueError(f"LLM did not return valid JSON: {response_text}") from e
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}. Response: {response_text if 'response_text' in locals() else 'N/A'}")
            raise
        except Exception as e:
            logger.error(f"Error generating content from LLM: {e}. Response: {response_text if 'response_text' in locals() else 'N/A'}")
            raise