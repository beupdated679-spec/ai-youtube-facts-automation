import os
import random
import subprocess
import requests
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

VIDEVO_API_URL = "https://api.videvo.net/v1/search"


def run(cmd):
    subprocess.run(cmd, check=True)


def extract_results(data):
    """
    Find video results in common Videvo API response formats.
    """
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in ("results", "data", "clips", "videos", "items"):
        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            for nested_key in ("results", "clips", "videos", "items"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return nested

    return []


def find_download_url(clip):
    """
    Extract a possible video download URL from a result.
    """
    if not isinstance(clip, dict):
        return None

    direct_fields = (
        "download_url",
        "downloadUrl",
        "url_hd",
        "url_sd",
        "video_url",
        "preview_url",
    )

    for field in direct_fields:
        value = clip.get(field)

        if isinstance(value, str) and value.startswith("http"):
            return value

    # Some APIs put download links inside nested objects.
    for field in ("download", "files", "video_files", "video"):
        value = clip.get(field)

        if isinstance(value, str) and value.startswith("http"):
            return value

        if isinstance(value, dict):
            for nested_value in value.values():
                if isinstance(nested_value, str) and nested_value.startswith("http"):
                    return nested_value

                if isinstance(nested_value, dict):
                    for item in nested_value.values():
                        if isinstance(item, str) and item.startswith("http"):
                            return item

        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.startswith("http"):
                    return item

                if isinstance(item, dict):
                    for nested_value in item.values():
                        if isinstance(nested_value, str) and nested_value.startswith("http"):
                            return nested_value

    return None


def fetch_videvo_clip(query, output_path):
    """
    Search Videvo and download one real video clip.
    """
    api_key = os.getenv("VIDEVO_API_KEY")

    if not api_key:
        raise RuntimeError("VIDEVO_API_KEY is missing from GitHub Secrets.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    params = {
        "query": query,
        "page": 1,
        "per_page": 20,
        "license_type": "free",
    }

    print(f"Searching Videvo for: {query}")

    response = requests.get(
        VIDEVO_API_URL,
        headers=headers,
        params=params,
        timeout=40,
    )

    print("Videvo search HTTP status:", response.status_code)

    if response.status_code == 401:
        raise RuntimeError("Videvo rejected the API key (HTTP 401).")

    if response.status_code == 403:
        raise RuntimeError("Videvo denied API access (HTTP 403).")

    if response.status_code == 429:
        raise RuntimeError("Videvo rate limit reached (HTTP 429).")

    response.raise_for_status()

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Videvo did not return valid JSON.")

    if isinstance(data, dict):
        print("Videvo response keys:", list(data.keys()))

    results = extract_results(data)

    if not results:
        raise RuntimeError(
            "Videvo returned no recognizable video results. "
            "Check the API response format and API access."
        )

    random.shuffle(results)

    for clip in results:
        if not isinstance(clip, dict):
            continue

        print("Available clip fields:", list(clip.keys()))

        video_url = find_download_url(clip)

        if not video_url:
            continue

        try:
            video_response = requests.get(
                video_url,
                timeout=90,
                stream=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            print("Video download HTTP status:", video_response.status_code)

            video_response.raise_for_status()

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            total_bytes = 0

            with output_path.open("wb") as file:
                for chunk in video_response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
                        total_bytes += len(chunk)

            if total_bytes < 10000:
                print("Downloaded file is too small; trying another result.")
                output_path.unlink(missing_ok=True)
                continue

            # Confirm that FFmpeg can recognize the downloaded video.
            check = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

            if check.returncode != 0 or not check.stdout.strip():
                print("Downloaded file is not a valid video; trying another result.")
                output_path.unlink(missing_ok=True)
                continue

            print(f"Downloaded real Videvo footage: {output_path}")
            return True

        except Exception as error:
            print("This Videvo result could not be downloaded:", error)
            Path(output_path).unlink(missing_ok=True)

    raise RuntimeError(
        f"No usable downloadable Videvo footage was found for: {query}. "
        "Check the GitHub Actions diagnostic logs."
    )


def get_font(size):
    """
    Load a font available in the GitHub Actions environment.
    """
    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]

    for font_path in possible_fonts:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size)

    return ImageFont.load_default()


def make_title_card(text, path, width, height):
    """
    Create a simple thumbnail background if a video frame
    cannot be extracted.
    """
    image = Image.new("RGB", (width, height), (13, 22, 42))
    draw = ImageDraw.Draw(image)

    font = get_font(max(30, width // 18))

    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        if draw.textbbox((0, 0), test, font=font)[2] < width * 0.82:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    line_height = max(40, height // 12)
    total_height = len(lines) * line_height
    y = (height - total_height) // 2

    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        x = (width - (box[2] - box[0])) // 2
        draw.text((x, y), line, fill="white", font=font)
        y += line_height

    image.save(path, quality=95)


def create_thumbnail(text, output_path, video_source=None,
                     width=1280, height=720):
    """
    Create a separate thumbnail using a real video frame
    whenever a source clip is available.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if video_source and Path(video_source).exists():
        try:
            run([
                "ffmpeg",
                "-y",
                "-ss", "1",
                "-i", str(video_source),
                "-frames:v", "1",
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                str(output_path),
            ])

            if output_path.exists() and output_path.stat().st_size > 1000:
                print("Thumbnail created from real video footage.")
                return

        except Exception as error:
            print("Could not extract thumbnail frame:", error)

    make_title_card(text, output_path, width, height)


def create_video(scenes, narration, voice_path, out_path,
                 work_dir, video_format, seconds):
    """
    Create a video using a different real Videvo clip for each scene.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    voice_path = Path(voice_path)

    if not voice_path.exists():
        raise RuntimeError(f"Voice file not found: {voice_path}")

    if not scenes:
        raise RuntimeError("AI did not provide any video scenes.")

    if video_format == "short":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080

    scene_duration = 3.0
    segments = []
    downloaded_sources = []

    # Make enough segments to cover the requested duration.
    segment_count = math.ceil(seconds / scene_duration)

    for i in range(segment_count):
        scene = scenes[i % len(scenes)]

        query = scene.get("visual_query") or scene.get("caption") or "science technology"

        source = work_dir / f"videvo_{i}.mp4"
        segment = work_dir / f"segment_{i}.mp4"

        print(f"Creating scene {i + 1}/{segment_count}")
        print("Visual search query:", query)

        fetch_videvo_clip(query, source)
        downloaded_sources.append(source)

        duration = min(scene_duration, seconds - i * scene_duration)

        run([
            "ffmpeg",
            "-y",
            "-stream_loop", "-1",
            "-i", str(source),
            "-t", str(duration),
            "-vf",
            (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},fps=30,format=yuv420p"
            ),
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            str(segment),
        ])

        segments.append(segment)

    if not segments:
        raise RuntimeError("No video segments were created.")

    concat_file = work_dir / "concat.txt"

    concat_file.write_text(
        "".join(f"file '{segment.resolve()}'\n" for segment in segments),
        encoding="utf-8",
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
        str(silent_video),
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
        str(out_path),
    ])

    print("Video successfully created:", out_path)

    return downloaded_sources[0]
