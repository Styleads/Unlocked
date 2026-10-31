import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).parent / ".env")

api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key)

print("Checking available Gemini models...\n")

for model in client.models.list():
    methods = getattr(model, "supported_actions", []) or []
    if "generateContent" in methods:
        print(model.name)