import json, os, sys, traceback
from pathlib import Path
from datetime import datetime, timezone
from modules.pipeline import run_pipeline

ROOT = Path(__file__).parent

def main():
    config = json.loads((ROOT / "config/channel.json").read_text(encoding="utf-8"))
    # Environment variables override safe configuration values.
    if os.getenv("GEMINI_MODEL"):
        config["gemini_model"] = os.environ["GEMINI_MODEL"]
    if os.getenv("YOUTUBE_PRIVACY_STATUS"):
        config["publish_privacy"] = os.environ["YOUTUBE_PRIVACY_STATUS"]

    try:
        result = run_pipeline(config, ROOT)
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
