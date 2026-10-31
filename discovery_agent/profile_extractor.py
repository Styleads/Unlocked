
import json


EXTRACTION_INSTRUCTIONS = """
You are the profile extraction component of Unlocked.

Unlocked supports farmers, students, entrepreneurs,
employees, unemployed people, senior citizens,
and all other members of the public.

Extract only facts explicitly stated in the user's latest message.

Never:
- Guess missing information.
- Invent personal details.
- Treat unknown information as false.
- Overwrite existing information unless the user explicitly
  corrects or updates it.

Organise information using these sections when relevant:

{
    "personal": {},
    "location": {},
    "education": {},
    "employment": {},
    "agriculture": {},
    "business": {},
    "household": {},
    "interests": [],
    "other_details": {}
}

Return valid JSON only.
Include only fields supported by the latest message.
"""


def extract_profile_update(client, model, user_message, current_profile):

    prompt = f"""
{EXTRACTION_INSTRUCTIONS}

EXISTING PROFILE:
{json.dumps(current_profile, ensure_ascii=False)}

LATEST USER MESSAGE:
{user_message}

Extract only newly stated or explicitly corrected facts.
Return a JSON object.
"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json"
        }
    )

    try:
        result = json.loads(response.text)

    except (json.JSONDecodeError, TypeError):
        raise ValueError("Gemini returned invalid JSON.")

    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object.")

    return result
