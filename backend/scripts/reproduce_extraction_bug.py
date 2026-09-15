import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Load .env
load_dotenv(backend_dir / ".env")
load_dotenv(backend_dir.parent / ".env")

from ai.providers.groq import GroqProvider
from ai.extractor import Extractor, _build_messages

raw_input = "Ali Test, ali.test.demo@gmail.com, 0477123456, 15/05/1985"
expected_field = "contact"

print("=" * 60)
print("REPRODUCING PRODUCTION BUG WITH REAL GROQ EXTRACTOR")
print(f"Input: {raw_input!r}")
print(f"Expected field: {expected_field!r}")
print("=" * 60)

provider = GroqProvider()
extractor = Extractor(provider)

# Let's also see what the raw LLM output is before parsing
messages = _build_messages(raw_input, expected_field)
print("\n--- Sending to Groq ---")
raw_response = provider.generate(messages, temperature=0.0, json_mode=True)
print(f"Raw Groq Response Content:\n{raw_response.content}\n")

# Now let's see what Extractor parses
event = extractor.extract(raw_input, expected_field=expected_field)
print("--- Parsed Event (Full 5-field) ---")
print(f"event.type: {event.type.value}")
print(f"event.entities: {event.entities}")

# Test partial input
event_partial = extractor.extract("Je m'appelle Nour", expected_field=expected_field)
print("\n--- Parsed Event (Partial input) ---")
print(f"event_partial.type: {event_partial.type.value}")
print(f"event_partial.entities: {event_partial.entities}")

# Test invalid date (downstream validation check)
event_date = extractor.extract("31/02/1990", expected_field=expected_field)
print("\n--- Parsed Event (Invalid date input) ---")
print(f"event_date.type: {event_date.type.value}")
print(f"event_date.entities: {event_date.entities}")
print("=" * 60)

