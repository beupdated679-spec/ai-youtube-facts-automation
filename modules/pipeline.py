import json
from pathlib import Path
from datetime import datetime, timezone

from .topic_finder import choose_topic
from .research import find_research
from .ai_writer import generate_video
from .voice import generate_voice
from .media import create_video, create_thumbnail
from .uploader import upload_video


def choose_format(config):
    strategy = config.get("format_strategy", "alternate")

    if strategy == "shorts_only":
        return "short"

    if strategy == "long_only":
        return "long"

    day = datetime.now(timezone.utc).timetuple().tm_yday

    return "short" if day % 2 else "long"


def run_pipeline(config, root: Path):

    root = Path(root)

    work = root / "work"
    output = root / "output"

    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    fmt = choose_format(config)

    print("Selected format:", fmt)

    topic = choose_topic(config)

    print("Selected topic:", topic)

    research = find_research(topic)

    data = generate_video(config, fmt, research)

    required = [
        "title",
        "description",
        "tags",
        "narration",
        "scenes"
    ]

    for key in required:
        if key not in data:
            raise RuntimeError(
                f"AI response missing required field: {key}"
            )

    if not data["scenes"]:
        raise RuntimeError("AI returned no scenes.")

    (output / "latest_script.txt").write_text(
        data["narration"],
        encoding="utf-8"
    )

    (output / "latest_metadata.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

    voice_path = work / "voice.mp3"

    generate_voice(
        data["narration"],
        voice_path,
        config.get("tts_voice", "en-US-AriaNeural")
    )

    if not voice_path.exists():
        raise RuntimeError("Voice generation failed.")

    seconds = int(
        config["short_seconds"]
        if fmt == "short"
        else config["long_seconds"]
    )

    video_path = output / f"daily_{fmt}.mp4"

    print("Starting video generation...")

    first_video_source = create_video(
        data["scenes"],
        data["narration"],
        voice_path,
        video_path,
        work,
        fmt,
        seconds
    )

    if not video_path.exists():
        raise RuntimeError("Video generation failed.")

    print("Video generated successfully.")

    thumb_path = output / "thumbnail.jpg"

    create_thumbnail(
        data.get("thumbnail_text") or data["title"],
        thumb_path,
        first_video_source
    )

    if not thumb_path.exists():
        raise RuntimeError("Thumbnail generation failed.")

    print("Thumbnail generated successfully.")

    print("Starting YouTube upload...")

    result = upload_video(
        video_path,
        data,
        thumb_path,
        config
    )

    report = {
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "topic": topic,
        "format": fmt,
        "title": data["title"],
        "research_reference": research.get("url", ""),
        "sources_returned_by_ai": data.get("sources", []),
        "upload": result
    }

    (output / "run_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print("SUCCESS:", json.dumps(report, indent=2))

    return report
