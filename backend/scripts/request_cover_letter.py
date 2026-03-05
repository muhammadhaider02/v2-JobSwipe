# request_cover_letter.py
"""Simple script to call the cover‑letter generation endpoint.

Run the Flask app (app.py) first so that the server is listening on
http://127.0.0.1:5000. Then execute this script:

    python request_cover_letter.py

It will POST a JSON payload containing `user_id`, `job_id` and the
`template_name` of a cover‑letter template stored under
`uploads/cover-letter-templates/`. The response JSON is printed to the
console.
"""

import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("The 'requests' library is required. Install it with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration – adjust these values to match data that exists in your
# Supabase tables.
# ---------------------------------------------------------------------------
API_URL = "http://127.0.0.1:5000/generate-cover-letter"
USER_ID = "b3c9e2c7-1c4c-5c2b-ac2b-2b3c4d5e6f7a"          # e.g. "b3c9e2c7-1c4c-5c2b-ac2b-2b3c4d5e6f7a"
JOB_ID ="0132d8c0-aeed-49e7-8642-17be2d606c2"            # e.g. "0132d8c0-aeed-49e7-8642-17be2d606c2"
TEMPLATE_NAME = "template1.txt"      # file name inside uploads/cover-letter-templates

payload = {
    "user_id": USER_ID,
    "job_id": JOB_ID,
    "template_name": TEMPLATE_NAME,
}

def main():
    try:
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Error contacting the service: {exc}")
        sys.exit(1)

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Response is not valid JSON:")
        print(response.text)
        sys.exit(1)

    # Pretty‑print the returned cover letter
    cover_letter = data.get("cover_letter")
    if cover_letter:
        print("--- Generated Cover Letter ---\n")
        print(cover_letter)
    else:
        print("Unexpected response format:")
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
