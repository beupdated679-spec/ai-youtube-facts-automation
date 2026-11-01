import json, os
from pathlib import Path
from datetime import datetime, timezone
import edge_tts
from .topic_finder import choose_topic
from .research import find_research
from .ai_writer import generate_video
from .voice import generate_voice
from .media import create_video, create_thumbnail
from .uploader import upload_video

def choose_format(config):
    strategy = config.get("format_strategy", "alternate")
    if strategy == "shorts_only": return "short"
    if strategy == "long_only": return "long"
    # Stable alternating pattern by UTC calendar day: odd=Short, even=long.
    day = datetime.now(timezone.utc).timetuple().tm_yday
    return "short" if day % 2 else "long"

def run_pipeline(config, root: Path):
    work = root / "work"
    output = root / "output"
    work.mkdir(exist_ok=True); output.mkdir(exist_ok=True)
    fmt = choose_format(config)
    print(f"Selected format: {fmt}")

    topic = choose_topic(config)
    print(f"Topic: {topic}")
    research = find_research(topic)
    data = generate_video(config, fmt, research)

    # Keep a copy of the script and metadata for review.
    (output / "latest_script.txt").write_text(data["narration"], encoding="utf-8")
    (output / "latest_metadata.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    voice_path = work / "voice.mp3"
    generate_voice(data["narration"], voice_path, config.get("tts_voice", "en-US-AriaNeural"))

    seconds = int(config["short_seconds"] if fmt == "short" else config["long_seconds"])
    video_path = output / f"daily_{fmt}.mp4"
    create_video(data["scenes"], data["narration"], voice_path, video_path,
                 work, fmt, seconds)

    thumb_path = output / "thumbnail.jpg"
    create_thumbnail(data.get("thumbnail_text") or data["title"], thumb_path)

    result = upload_video(video_path, data, thumb_path, config)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "topic": topic, "format": fmt, "title": data["title"],
        "research_reference": research.get("url", ""),
        "sources_returned_by_ai": data.get("sources", []),
        "upload": result
    }
    (output / "run_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("SUCCESS:", json.dumps(report, indent=2))
    return report
