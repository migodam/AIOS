from pydantic import ValidationError
from aios.protocols.schema import Receipt

try:
    print("Attempting to create Receipt with invalid status 'pending'...")
    receipt = Receipt(action_id="123", status="pending", message="test", latency_ms=0.0)
    print("... succeeded unexpectedly. Here is the receipt:")
    print(receipt)
except ValidationError as e:
    print("... failed as expected. Validation error:")
    print(e)
except Exception as e:
    print(f"... failed with an unexpected error: {e}")
