# AI YouTube Facts Automation (USA)

A GitHub Actions project that creates **one original Facts & Knowledge video per day** for a US audience, alternating between a Short and a longer video, then uploads it through the official YouTube Data API.

## What it does
1. Chooses a topic from the configured Facts & Knowledge categories.
2. Retrieves a Wikipedia summary as a research starting point.
3. Uses Gemini to write an original American-English script, scene plan, title, description and tags.
4. Downloads relevant stock clips from Pexels (or uses generated title cards if no clip is available).
5. Generates American-English narration with Edge TTS.
6. Renders a vertical Short (about 45 seconds) or a horizontal long video (about 3 minutes), with burned-in captions.
7. Creates a thumbnail and uploads the video to YouTube.
8. Saves a run report and generated files as a GitHub Actions artifact.

**Important:** This is an automated first version, not a guarantee of factual correctness or viral performance. Review early outputs. Wikipedia is a research starting point, not proof of every claim. Do not publish claims you cannot verify. Use only licensed footage/music. The project does not include background music by default.

## Daily format
The default schedule is **one video per day**, alternating Shorts and long videos based on the date. Change `format_strategy` in `config/channel.json` if you want a different pattern.

## Requirements / accounts
- GitHub account and a repository.
- Google AI Studio API key for Gemini. Check current free-tier availability and limits in your region.
- Pexels API key (optional but recommended; check Pexels terms and API limits).
- Google Cloud project with YouTube Data API v3 enabled.
- YouTube OAuth client and a refresh token for the channel you own/manage.

No API key is embedded in this repository. Never commit credentials.

## 1) Create the YouTube API credentials
1. Open Google Cloud Console: https://console.cloud.google.com/
2. Create a project and enable **YouTube Data API v3**.
3. Configure the OAuth consent screen as required by Google.
4. Create an OAuth Client ID of type **Desktop app** and download the client JSON.
5. Save it locally as `client_secret.json` in the project root.
6. Install dependencies locally: `pip install -r requirements.txt`.
7. Run: `python scripts/get_youtube_refresh_token.py`
8. Sign in to the correct channel and approve the YouTube upload permission.
9. Copy the refresh token printed by the script. Treat it like a password.

Google's official upload guide: https://developers.google.com/youtube/data/guides/uploading_a_video

## 2) Add GitHub Actions secrets
In your GitHub repository:
**Settings → Secrets and variables → Actions → New repository secret**

Add:
- `GEMINI_API_KEY` — Google AI Studio key.
- `PEXELS_API_KEY` — optional, but recommended.
- `YOUTUBE_CLIENT_ID` — OAuth client ID.
- `YOUTUBE_CLIENT_SECRET` — OAuth client secret.
- `YOUTUBE_REFRESH_TOKEN` — refresh token from step 1.

Do not put these values in `channel.json`, code, screenshots or public issues.

## 3) Upload this project to GitHub
Create a repository named `ai-youtube-facts-automation`, upload all files from this folder, and use the default branch `main`.

## 4) Enable and run
1. Open **Actions** in your repository and enable workflows if GitHub asks.
2. Open **AI YouTube Daily Publisher**.
3. Choose **Run workflow** to test manually.
4. The scheduled run is daily at 17:00 UTC (approximately noon Eastern Standard Time / 1 PM Eastern Daylight Time).
5. The rendered MP4, thumbnail, script and report are uploaded as an Actions artifact.

GitHub scheduled workflows use UTC here. Runs can be delayed by GitHub and are not guaranteed to start at the exact minute.

## 5) Configuration
Edit `config/channel.json`:
- `channel_category`: keep `Facts & Knowledge` or change subtopics.
- `format_strategy`: `alternate` (default), `shorts_only`, or `long_only`.
- `short_seconds`: default 45.
- `long_seconds`: default 180.
- `publish_privacy`: `public` for automatic public publishing; use `private` while testing.
- `made_for_kids`: set truthfully for the actual intended audience. Do not select this just because the video is family-friendly.

## 6) First test recommendation
Before enabling public publishing, set `"publish_privacy": "private"` and run manually. Watch the whole video, verify facts, check the thumbnail and description, and confirm you have rights to the footage. Then change it to `public` if appropriate.

## Known limits
- GitHub Actions free minutes/storage depend on your account and repository visibility.
- Gemini and Pexels usage limits/availability can change; check their current terms.
- Edge TTS is a community Python client for Microsoft's online speech service; availability and terms may change. It is not a guaranteed commercial TTS entitlement.
- If the YouTube API OAuth app is in testing mode, Google may limit who can authorize it. Follow the current Google verification/consent-screen requirements.
- Some API projects or channel/account settings may restrict public uploads. If a video arrives as private despite `public` being configured, check the YouTube API project's verification/audit status and channel settings.
- The bot creates videos from stock clips and captions; it does not generate bespoke AI video footage.
- No music is added by default. Add only music you own or are licensed to use.

## Troubleshooting
- **Missing secrets:** check exact secret names under repository Actions secrets.
- **Gemini error:** verify key, model availability and account limits. Set `GEMINI_MODEL` if needed.
- **No Pexels clips:** verify `PEXELS_API_KEY`; title-card fallback should still render.
- **FFmpeg error:** workflow installs FFmpeg. For local use, install FFmpeg and ensure `ffmpeg` and `ffprobe` are on PATH.
- **OAuth error:** repeat the refresh-token setup using the correct Google OAuth Desktop client and channel.
- **Public upload becomes private:** check the API project and channel restrictions before assuming the workflow failed.

## Responsible publishing
The script asks Gemini for original writing and source URLs, but the bot cannot guarantee every generated claim is correct. Review facts, attribution, copyright, and synthetic-media disclosure requirements. Avoid repetitive, mass-produced or misleading content. Use YouTube's disclosure setting when a video contains realistic altered/synthetic content that requires disclosure.
