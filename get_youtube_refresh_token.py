"""Run locally once to obtain a YouTube upload refresh token."""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parents[1]
CLIENT_FILE = ROOT / "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

if not CLIENT_FILE.exists():
    raise SystemExit("Put your downloaded Google OAuth Desktop client JSON at client_secret.json")
flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nSAVE THESE AS GITHUB ACTIONS SECRETS:")
print("YOUTUBE_CLIENT_ID =", credentials.client_id)
print("YOUTUBE_CLIENT_SECRET =", credentials.client_secret)
print("YOUTUBE_REFRESH_TOKEN =", credentials.refresh_token)
if not credentials.refresh_token:
    print("WARNING: No refresh token returned. Revoke the app's access in your Google Account and run again.")
