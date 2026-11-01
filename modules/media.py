import os
import re
import math
import time
import random
import subprocess
import requests

from pathlib import Path
from urllib.parse import urlparse


UNSPLASH_API = "https://api.unsplash.com"
APP_NAME = "ai_youtube_facts_automation"


def run(cmd):
    subprocess.run(cmd, check=True)


def get_headers():
    key = os.getenv("UNSPLASH_ACCESS_KEY")

    if not key:
        raise RuntimeError(
            "UNSPLASH_ACCESS_KEY is missing from GitHub Secrets."
        )

    return {
        "Authorization": f"Client-ID {key}",
        "Accept-Version": "v1"
    }


def search_unsplash(query, orientation="landscape"):
    headers = get_headers()

    print("Searching Unsplash for:", query)

    for attempt in range(4):
        try:
            response = requests.get(
                f"{UNSPLASH_API}/search/photos",
                headers=headers,
                params={
                    "query": query,
                    "page": 1,
                    "per_page": 10,
                    "orientation": orientation,
                    "content_filter": "high"
                },
                timeout=40
            )

            if response.status_code == 429:
                raise RuntimeError(
                    "Unsplash rate limit reached. Try again later."
                )

            response.raise_for_status()

            results = response.json().get("results", [])

            if not results:
                raise RuntimeError(
                    f"No Unsplash photographs found for: {query}"
                )

            return results

        except requests.RequestException as error:
            if attempt == 3:
                raise RuntimeError(
                    f"Unsplash search failed: {error}"
                ) from error

            delay = 3 * (attempt + 1)
            print(f"Search retry in {delay} seconds.")
            time.sleep(delay)

    raise RuntimeError("Unsplash search failed.")


def track_download(photo):
    download_url = (
        photo.get("links", {}).get("download_location")
    )

    if not download_url:
        raise RuntimeError(
            "Unsplash did not provide a download tracking URL."
        )

    response = requests.get(
        download_url,
        headers=get_headers(),
        params={
            "utm_source": APP_NAME,
            "utm_medium": "referral"
        },
        timeout=30
    )

    response.raise_for_status()


def get_photo(query, orientation, used_ids):
    results = search_unsplash(query, orientation)

    available = [
        photo for photo in results
        if photo.get("id") not in used_ids
        and photo.get("urls", {}).get("regular")
    ]

    if not available:
        available = [
            photo for photo in results
            if photo.get("urls", {}).get("regular")
        ]

    if not available:
        raise RuntimeError(
            f"No usable Unsplash photo for: {query}"
        )

    photo = random.choice(available)

    # Required Unsplash download event.
    track_download(photo)

    image_url = photo["urls"]["regular"]

    username = photo.get("user", {}).get(
        "username", "unknown"
    )

    name = photo.get("user", {}).get(
        "name", "Unknown photographer"
    )

    profile = (
        f"https://unsplash.com/@{username}"
        f"?utm_source={APP_NAME}&utm_medium=referral"
    )

    photo_link = photo.get("links", {}).get("html", "")

    used_ids.add(photo.get("id"))

    return {
        "url": image_url,
        "id": photo.get("id"),
        "name": name,
        "profile": profile,
        "photo_link": photo_link
    }


def get_font_path():
    fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
    ]

    for font in fonts:
        if Path(font).exists():
            return font

    return None


def create_thumbnail(
    text,
    output_path,
    video_source=None,
    width=1280,
    height=720
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not video_source:
        raise RuntimeError(
            "A real Unsplash image is required for the thumbnail."
        )

    image_url = str(video_source)

    command = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", image_url,
        "-frames:v", "1",
        "-vf",
        (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    ]

    font = get_font_path()

    if font:
        text_file = output_path.parent / "thumbnail_text.txt"
        text_file.write_text(
            str(text)[:65].replace("\n", " "),
            encoding="utf-8"
        )

        command.extend([
            "-vf",
            (
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"drawtext=fontfile='{font}':"
                f"textfile='{text_file}':"
                "fontcolor=white:fontsize=65:"
                "x=(w-text_w)/2:y=h*0.76:"
                "box=1:boxcolor=black@0.55:boxborderw=18"
            )
        ])

    command.extend([
        "-q:v", "2",
        str(output_path)
    ])

    run(command)

    if not output_path.exists() or output_path.stat().st_size < 1000:
        raise RuntimeError("Thumbnail creation failed.")

    print("Real Unsplash thumbnail created.")


def create_video(
    scenes,
    narration,
    voice_path,
    out_path,
    work_dir,
    video_format,
    seconds
):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    voice_path = Path(voice_path)

    if not voice_path.exists():
        raise RuntimeError(
            f"Voice file not found: {voice_path}"
        )

    if not scenes:
        raise RuntimeError("No scenes were supplied by Gemini.")

    if video_format == "short":
        width, height = 1080, 1920
        orientation = "portrait"
    else:
        width, height = 1920, 1080
        orientation = "landscape"

    scene_duration = 3.0
    segment_count = math.ceil(seconds / scene_duration)

    segments = []
    used_ids = set()
    attribution = []
    first_image_url = None

    attribution_file = (
        work_dir / "unsplash_attribution.txt"
    )

    for i in range(segment_count):

        scene = scenes[i % len(scenes)]

        query = (
            scene.get("visual_query")
            or scene.get("caption")
            or "science technology"
        )

        print(
            f"Creating scene {i + 1}/{segment_count}"
        )
        print("Visual search query:", query)

        photo = get_photo(
            query,
            orientation,
            used_ids
        )

        image_url = photo["url"]

        if first_image_url is None:
            first_image_url = image_url

        attribution.append(
            f"Photo by {photo['name']}\n"
            f"Photographer profile: {photo['profile']}\n"
            f"Photo: {photo['photo_link']}\n"
            f"Source: Unsplash\n"
        )

        duration = min(
            scene_duration,
            seconds - i * scene_duration
        )

        frames = max(1, round(duration * 30))

        segment = work_dir / f"segment_{i}.mp4"

        print("Creating moving photograph.")

        zoom_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0008,1.08)':"
            f"d=1:s={width}x{height}:fps=30,"
            "format=yuv420p"
        )

        run([
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", image_url,
            "-t", str(duration),
            "-vf", zoom_filter,
            "-r", "30",
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(segment)
        ])

        if not segment.exists() or segment.stat().st_size < 1000:
            raise RuntimeError(
                f"Video segment {i + 1} was not created."
            )

        segments.append(segment)

    attribution_file.write_text(
        "\n".join(attribution),
        encoding="utf-8"
    )

    concat_file = work_dir / "concat.txt"

    concat_file.write_text(
        "".join(
            f"file '{segment.resolve()}'\n"
            for segment in segments
        ),
        encoding="utf-8"
    )

    silent_video = work_dir / "silent_video.mp4"

    run([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(silent_video)
    ])

    run([
        "ffmpeg",
        "-y",
        "-i", str(silent_video),
        "-i", str(voice_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        str(out_path)
    ])

    if not out_path.exists() or out_path.stat().st_size < 10000:
        raise RuntimeError("Final video was not created correctly.")

    print("Unsplash video successfully created:", out_path)
    print("Attribution file:", attribution_file)

    return first_image_url
