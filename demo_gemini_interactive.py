
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load API key
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path, override=True)

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("Google API key not found!")

client = genai.Client(api_key=api_key)

MODEL = "gemini-flash-lite-latest"

SYSTEM_INSTRUCTION = """
You are the Discovery Agent for Unlocked.

Unlocked helps people discover government schemes
and benefits they may be eligible to apply for.

Your responsibilities:
1. Understand the user through natural conversation.
2. Remember information shared earlier in the conversation.
3. Ask relevant follow-up questions.
4. Do not ask for information the user has already provided.
5. Never assume missing information.
6. Never invent schemes or eligibility requirements.
7. Explain why you need information when asking personal questions.

Start by greeting the user and asking what kind of
government benefits they want to explore.
"""

# Create a conversation session
chat = client.chats.create(
    model=MODEL,
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION
    )
)

print("\n===== UNLOCKED DISCOVERY AGENT =====")
print("Conversation started!")
print("Type 'exit' to stop.\n")

try:
    while True:
        user_message = input("You: ").strip()

        if user_message.lower() == "exit":
            print("Unlocked: Thank you! See you soon.")
            break

        if not user_message:
            continue

        try:
            response = chat.send_message(user_message)
            print("\nUnlocked:", response.text, "\n")

        except Exception as error:
            print("\nSomething went wrong:", error)

finally:
    client.close()

