import os
import requests
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

VIDEVO_API_URL = "https://api.videvo.net/v1/search"

def run(cmd):
    subprocess.run(cmd, check=True)

def fetch_videvo_clip(query, output_path):
    api_key = os.getenv("VIDEVO_API_KEY")

    if not api_key:
        print("VIDEVO_API_KEY is missing")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    params = {
        "query": query,
        "page": 1,
        "per_page": 10,
        "license_type": "free"
    }

    try:
        response = requests.get(
            VIDEVO_API_URL,
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])

        if not results:
            print("No Videvo clips found")
            return False

        clip = results[0]
        video_url = clip.get("download_url") or clip.get("url")

        if not video_url:
            print("No downloadable video URL returned")
            return False

        video = requests.get(video_url, timeout=60)
        video.raise_for_status()

        Path(output_path).write_bytes(video.content)
        return True

    except Exception as error:
        print("Videvo error:", error)
        return False


def get_font(size):
    return ImageFont.load_default()


def make_title_card(text, path, width, height):
    image = Image.new("RGB", (width, height), (13, 22, 42))
    draw = ImageDraw.Draw(image)
    font = get_font(40)

    draw.text(
        (width // 10, height // 2),
        text[:100],
        fill="white",
        font=font
    )

    image.save(path)


def create_thumbnail(text, output_path, width=1280, height=720):
    make_title_card(text, output_path, width, height)


def create_video(scenes, narration, voice_path, out_path,
                 work_dir, video_format, seconds):

    work_dir.mkdir(parents=True, exist_ok=True)

    width, height = (
        (1080, 1920) if video_format == "short"
        else (1920, 1080)
    )

    segments = []
    scene_duration = seconds / max(1, len(scenes))

    for i, scene in enumerate(scenes):
        source = work_dir / f"videvo_{i}.mp4"
        segment = work_dir / f"segment_{i}.mp4"

        success = fetch_videvo_clip(
            scene.get("visual_query", "nature science"),
            source
        )

        if success:
            run([
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", str(source),
                "-t", str(scene_duration),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30",
                "-an",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(segment)
            ])
        else:
            card = work_dir / f"card_{i}.jpg"
            make_title_card(
                scene.get("caption", "Amazing Facts"),
                card, width, height
            )

            run([
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(card),
                "-t", str(scene_duration),
                "-r", "30",
                "-vf", f"scale={width}:{height},format=yuv420p",
                "-c:v", "libx264",
                str(segment)
            ])

        segments.append(segment)

    concat_file = work_dir / "concat.txt"

    concat_file.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in segments)
    )

    silent_video = work_dir / "silent.mp4"

    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(silent_video)
    ])

    run([
        "ffmpeg", "-y",
        "-i", str(silent_video),
        "-i", str(voice_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(out_path)
    ])
