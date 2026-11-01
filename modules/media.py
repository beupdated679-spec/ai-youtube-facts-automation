import os
import math
import random
import textwrap
import requests
import subprocess

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


VIDEVO_API_URL = "https://api.videvo.net/v1/search"
IMAGE_INTERVAL = 3
VIDEO_FPS = 30


def run(cmd):
    subprocess.run(cmd, check=True)


def get_font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for font_path in candidates:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size=size)

    return ImageFont.load_default()


def extract_results(data):
    """Accept common search-result response structures."""
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in ("results", "data", "videos", "items"):
        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            for nested in ("results", "videos", "items"):
                if isinstance(value.get(nested), list):
                    return value[nested]

    return []


def fetch_videvo_clip(query, output_path, page=1):
    api_key = os.getenv("VIDEVO_API_KEY")

    if not api_key:
        raise RuntimeError("Missing VIDEVO_API_KEY GitHub secret.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    params = {
        "query": query,
        "page": page,
        "per_page": 10,
        "license_type": "free"
    }

    response = requests.get(
        VIDEVO_API_URL,
        headers=headers,
        params=params,
        timeout=45
    )

    response.raise_for_status()

    results = extract_results(response.json())

    if not results:
        print(f"No Videvo results for: {query}")
        return False

    random.shuffle(results)

    for clip in results:
        if not isinstance(clip, dict):
            continue

        video_url = (
            clip.get("download_url")
            or clip.get("downloadUrl")
            or clip.get("video_url")
            or clip.get("url")
        )

        if not video_url:
            continue

        try:
            video = requests.get(
                video_url,
                timeout=90,
                stream=True
            )

            video.raise_for_status()

            content_type = video.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" in content_type:
                print("Skipping webpage instead of video.")
                video.close()
                continue

            output_path = Path(output_path)
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            with output_path.open("wb") as file:
                for chunk in video.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)

            video.close()

            if output_path.stat().st_size < 10000:
                output_path.unlink(missing_ok=True)
                continue

            print(f"Downloaded footage for: {query}")
            return True

        except Exception as error:
            print("Download candidate failed:", error)
            Path(output_path).unlink(missing_ok=True)

    return False


def make_title_card(text, path, width, height):
    """Create a separate designed thumbnail, not a video background."""
    image = Image.new(
        "RGB",
        (width, height),
        (13, 22, 42)
    )

    draw = ImageDraw.Draw(image)
    font = get_font(max(35, width // 17))

    words = textwrap.wrap(str(text)[:100], width=24)

    y = height // 2 - (len(words) * width // 25)

    for line in words[:4]:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]

        x = (width - text_width) // 2

        draw.text(
            (x + 3, y + 3),
            line,
            fill=(0, 0, 0),
            font=font
        )

        draw.text(
            (x, y),
            line,
            fill=(255, 255, 255),
            font=font
        )

        y += width // 12

    image.save(path, quality=95)


def create_thumbnail(text, output_path, width=1280, height=720):
    """
    Use a real video frame as thumbnail background
    and independently design the thumbnail text.
    """
    output_path = Path(output_path)

    root = output_path.parent.parent
    background = root / "work" / "thumbnail_background.jpg"

    if background.exists():
        image = Image.open(background).convert("RGB")

        image_ratio = image.width / image.height
        target_ratio = width / height

        if image_ratio > target_ratio:
            new_width = int(image.height * target_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((
                left, 0, left + new_width, image.height
            ))
        else:
            new_height = int(image.width / target_ratio)
            top = (image.height - new_height) // 2
            image = image.crop((
                0, top, image.width, top + new_height
            ))

        image = image.resize((width, height))

    else:
        image = Image.new(
            "RGB",
            (width, height),
            (13, 22, 42)
        )

    draw = ImageDraw.Draw(image)
    font = get_font(65)

    draw.rectangle(
        (0, height - 230, width, height),
        fill=(0, 0, 0, 180)
    )

    lines = textwrap.wrap(str(text)[:90], width=27)

    y = height - 190

    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2

        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255)
        )

        y += 75

    image.save(output_path, quality=95)
    print("Separate thumbnail created:", output_path)


def create_video(
    scenes,
    narration,
    voice_path,
    out_path,
    work_dir,
    video_format,
    seconds
):
    work_dir.mkdir(parents=True, exist_ok=True)

    out_path = Path(out_path)

    width, height = (
        (1080, 1920)
        if video_format == "short"
        else (1920, 1080)
    )

    # One visual segment for approximately every 3 seconds.
    segment_count = math.ceil(seconds / IMAGE_INTERVAL)

    if not scenes:
        raise RuntimeError("No AI scenes were supplied.")

    print(
        f"Creating {segment_count} visual segments "
        f"at approximately {IMAGE_INTERVAL}-second intervals."
    )

    segments = []

    thumbnail_saved = False

    for i in range(segment_count):
        scene = scenes[i % len(scenes)]

        query = scene.get("visual_query", "").strip()

        if not query:
            query = "science technology nature documentary"

        duration = min(
            IMAGE_INTERVAL,
            seconds - (i * IMAGE_INTERVAL)
        )

        source = work_dir / f"videvo_{i}.mp4"
        segment = work_dir / f"segment_{i}.mp4"

        print(
            f"Fetching visual {i + 1}/{segment_count}: {query}"
        )

        success = False

        # Try several pages before declaring footage unavailable.
        for page in range(1, 4):
            try:
                success = fetch_videvo_clip(
                    query,
                    source,
                    page=page
                )

                if success:
                    break

            except Exception as error:
                print(
                    f"Videvo page {page} failed: {error}"
                )

        if not success:
            raise RuntimeError(
                f"No real Videvo footage could be downloaded "
                f"for scene {i + 1}: {query}. "
                f"Stopping instead of creating a blue background."
            )

        # Extract a real video frame for a separate thumbnail.
        if not thumbnail_saved:
            thumbnail_frame = (
                work_dir / "thumbnail_background.jpg"
            )

            try:
                run([
                    "ffmpeg", "-y",
                    "-ss", "1",
                    "-i", str(source),
                    "-frames:v", "1",
                    "-q:v", "2",
                    str(thumbnail_frame)
                ])

                thumbnail_saved = thumbnail_frame.exists()

            except Exception as error:
                print("Thumbnail frame extraction failed:", error)

        # Convert each downloaded clip into a 3-second segment.
        run([
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(source),
            "-t", str(duration),
            "-vf",
            (
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"fps={VIDEO_FPS},"
                "setsar=1"
            ),
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(segment)
        ])

        segments.append(segment)

        print(
            f"Visual segment {i + 1}/{segment_count} completed."
        )

    # Combine all video segments.
    concat_file = work_dir / "concat.txt"

    concat_file.write_text(
        "".join(
            f"file '{p.resolve()}'\n"
            for p in segments
        ),
        encoding="utf-8"
    )

    silent_video = work_dir / "silent.mp4"

    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(silent_video)
    ])

    # Add the generated voice narration.
    run([
        "ffmpeg", "-y",
        "-i", str(silent_video),
        "-i", str(voice_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path)
    ])

    print("Video created successfully:", out_path)
