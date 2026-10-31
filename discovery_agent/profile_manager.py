
import json
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parent.parent / "user_profile.json"


def load_profile():
    if not PROFILE_PATH.exists():
        return {}

    try:
        with open(PROFILE_PATH, "r", encoding="utf-8-sig") as file:
            profile = json.load(file)

        if not isinstance(profile, dict):
            raise ValueError("Profile file must contain a JSON object.")

        return profile

    except json.JSONDecodeError:
        raise ValueError(
            "user_profile.json contains invalid JSON. "
            "Please check the file before continuing."
        )


def merge_profiles(existing, updates):
    merged = existing.copy()

    for key, value in updates.items():

        # Ignore unknown or empty values
        if value is None or value == "":
            continue

        if isinstance(value, dict):
            old_value = merged.get(key, {})

            if not isinstance(old_value, dict):
                old_value = {}

            merged[key] = merge_profiles(old_value, value)

        elif isinstance(value, list):
            old_value = merged.get(key, [])

            if not isinstance(old_value, list):
                old_value = []

            # Preserve existing items without duplicates
            merged[key] = list(dict.fromkeys(old_value + value))

        else:
            # New explicitly stated information can update old information
            merged[key] = value

    return merged


def save_profile(profile):
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(PROFILE_PATH, "w", encoding="utf-8") as file:
        json.dump(
            profile,
            file,
            indent=4,
            ensure_ascii=False
        )


def update_profile(updates):
    current_profile = load_profile()
    updated_profile = merge_profiles(current_profile, updates)
    save_profile(updated_profile)

    return updated_profile
