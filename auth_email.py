"""One-time Gmail authorization for Morning Check-in.

Run this once PER ACCOUNT, in your own terminal (it opens a browser window):

    ./venv/bin/python auth_email.py juyeonma@umich.edu
    ./venv/bin/python auth_email.py majuyeon695@gmail.com

Requires credentials.json (your Google OAuth "Desktop app" client) in this
folder — see SETUP_EMAIL.md. Saves token_<account>.json, which the app then
uses read-only. Re-run for an account anytime to re-authorize.
"""
import sys
from email_handler import CREDENTIALS_PATH, SCOPES, token_path


def main():
    if len(sys.argv) != 2:
        print("Usage:  python auth_email.py you@example.com")
        sys.exit(1)
    account = sys.argv[1].strip()

    if not CREDENTIALS_PATH.exists():
        print(f"Missing {CREDENTIALS_PATH.name}.")
        print("Download your OAuth client (type: Desktop app) from Google Cloud")
        print(f"and save it here as credentials.json. See SETUP_EMAIL.md.")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, login_hint=account, prompt="consent")

    tp = token_path(account)
    tp.write_text(creds.to_json())
    print(f"\n  Authorized {account}  →  saved {tp.name}")
    print("  Open http://127.0.0.1:5001 and your emails will appear. 🌿\n")


if __name__ == "__main__":
    main()
