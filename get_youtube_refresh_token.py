import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]

CLIENT_ID = os.environ["YOUTUBE_CLIENT_ID"]
CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}

flow = InstalledAppFlow.from_client_config(
    client_config,
    SCOPES
)

credentials = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent"
)

if not credentials.refresh_token:
    raise RuntimeError("No refresh token received. Authorize again.")

print("\nYour YouTube refresh token was generated.")
print(credentials.refresh_token)
