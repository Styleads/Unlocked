
import os
from dotenv import load_dotenv
from google import genai

from discovery_agent.search_provider import search_web
from discovery_agent.scheme_extractor import extract_schemes

load_dotenv()

MODEL = "gemini-3.5-flash-lite"

query = (
    "official Karnataka farmer crop insurance schemes "
    "government portal"
)

print("\n1. Searching with Tavily...")
results = search_web(query, 5)

print(f"Retrieved {len(results)} results")

print("\n2. Sending results to Gemini...")

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    schemes = extract_schemes(
        client,
        MODEL,
        results,
        user_context={
            "employment": {"occupation": "farmer"},
            "location": {
                "district": "Mandya",
                "state": "Karnataka"
            },
            "interests": ["crop insurance"]
        }
    )

    print(f"\n3. Extracted {len(schemes)} schemes")

    for scheme in schemes:
        print("\n" + "=" * 50)
        print("NAME:", scheme.name)
        print("RELEVANCE:", scheme.relevance)
        print("VERIFICATION:", scheme.verification_status)
        print("OFFICIAL URL:", scheme.official_url)

        print("\nCLAIMS:")
        for claim in scheme.claims:
            print("-", claim.claim)
            print("  Status:", claim.verification_status)
            print("  Source:", claim.source_url)

finally:
    client.close()
