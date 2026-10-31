"""
Conversational Discovery Agent interface for Unlocked.

Interacts with users to learn about their background, update
their stored profile, and guide them through benefits discovery.
"""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from discovery_agent.profile_extractor import extract_profile_update
from discovery_agent.profile_manager import load_profile, update_profile

logger = logging.getLogger(__name__)

# --------------------------------------------------
# Instructions for conversational agent
# --------------------------------------------------

SYSTEM_INSTRUCTION = """
You are Unlocked, a universal government benefits discovery assistant.

You help people discover potentially relevant government schemes.

You can assist:
- Farmers
- Students
- Entrepreneurs and business owners
- Employed and unemployed people
- Senior citizens
- Women
- Persons with disabilities
- Other members of the public

YOUR RULES:
1. Speak naturally and conversationally.
2. Understand the user's circumstances before suggesting schemes.
3. Ask only relevant follow-up questions.
4. Do not repeatedly ask for information already provided.
5. Never assume missing information.
6. Never invent government schemes or eligibility requirements.
7. Explain why you need personal information.
8. A person can belong to multiple categories.
9. Do not claim someone is eligible without verified requirements.
10. For now, focus on understanding the user. Scheme searching
    will be added in a later development stage.
"""

MODEL = "gemini-3.5-flash-lite"


def create_agent_chat(api_key: str | None = None, model: str = MODEL):
    """Create and return a Gemini chat session for the conversational agent."""
    if not api_key:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(env_path, override=True)
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("Google API key not found!")

    client = genai.Client(api_key=api_key)
    chat = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION
        )
    )
    return client, chat


def run_agent():
    """Run the interactive console chat loop."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, override=True)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in environment or .env file.")
        return

    client, chat = create_agent_chat(api_key)
    profile = load_profile()

    print("\n===================================")
    print("       UNLOCKED DISCOVERY AGENT")
    print("===================================")
    print("Gemini connected.")
    print("Profile loaded.")
    print("Commands: /profile | /exit\n")

    try:
        while True:
            try:
                user_message = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nUnlocked: Goodbye!")
                break

            if not user_message:
                continue

            if user_message.lower() == "/exit":
                print("\nUnlocked: Goodbye! Your profile has been saved.")
                break

            # Display the currently saved profile
            if user_message.lower() == "/profile":
                print("\n--- SAVED USER PROFILE ---")
                print(json.dumps(profile, indent=4, ensure_ascii=False))
                print("--------------------------\n")
                continue

            # Extract new information from user's message
            try:
                updates = extract_profile_update(
                    client,
                    MODEL,
                    user_message,
                    profile
                )
                profile = update_profile(updates)
                print("[Profile updated and saved]")
            except Exception as error:
                logger.warning("Profile extraction warning: %s", error)
                print("[Continuing conversation anyway]")

            # Give Gemini latest known profile as context
            profile_context = json.dumps(
                profile,
                ensure_ascii=False
            )

            message_with_context = f"""
KNOWN USER PROFILE:
{profile_context}

NEW USER MESSAGE:
{user_message}
"""

            try:
                response = chat.send_message(message_with_context)
                print("\nUnlocked:", response.text, "\n")
            except Exception as error:
                print("\nResponse error:", error)
                print("Please try again.\n")

    finally:
        client.close()


if __name__ == "__main__":
    run_agent()
