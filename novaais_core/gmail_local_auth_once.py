"""
Run this ONCE locally (Cloud Shell) to generate token.json for Gmail OAuth.

This authenticates the AI Gmail account (tstngallen@gmail.com) and stores:
    novaais_core/token.json

Cloud Run will then load token.json automatically and send/forward emails.
"""

import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail scopes (send + read + modify)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly"
]

ROOT = Path(__file__).parent
CREDENTIALS = ROOT / "credentials.json"
TOKEN = ROOT / "token.json"

def main():
    print("📌 Starting Gmail OAuth Setup...")

    if not CREDENTIALS.exists():
        print("❌ ERROR: credentials.json not found in novaais_core/")
        print("Make sure you saved the OAuth credentials file as:")
        print("  novaais_core/credentials.json")
        return

    creds = None

    if TOKEN.exists():
        print("🔄 token.json already exists—loading it...")
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🌐 Opening browser for Gmail login...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN, "w") as token_file:
            token_file.write(creds.to_json())
            print("✅ token.json created successfully!")

    print("🎉 Gmail OAuth setup complete.")
    print("AI Gmail account is now authenticated.")

if __name__ == "__main__":
    main()
