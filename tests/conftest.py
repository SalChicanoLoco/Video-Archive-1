import os

# Provide dummy values so startup validation passes in tests.
# Tests that actually hit Airtable or Anthropic must mock those services.
os.environ.setdefault("AIRTABLE_API_KEY", "test_dummy")
os.environ.setdefault("AIRTABLE_BASE_ID", "test_dummy")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_dummy")
