import os, re, subprocess, requests, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def get_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

def make_title_card(text, path, width, height):
    img = Image.new("RGB", (width, height), (13, 22, 42))
    draw = ImageDraw.Draw(img)
    font = get_font(max(34, width // 14))
    words, lines, current = text.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0,0), test, font=font)[2] > width - 100:
            lines.append(current); current = word
        else:
            current = test
    if current: lines.append(current)
    y = height // 2 - (len(lines) * (font.size + 18)) // 2
    for line in lines:
        box = draw.textbbox((0,0), line, font=font)
        x = (width - (box[2]-box[0])) // 2
        draw.text((x+3, y+3), line, font=font, fill=(0,0,0))
        draw.text((x, y), line, font=font, fill=(255,255,255))
        y += font.size + 18
    img.save(path, quality=92)

def fetch_pexels_clip(query, out_path):
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return False
    headers = {"Authorization": key}
    params = {"query": query or "nature science technology", "per_page": 5, "orientation": "portrait"}
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=30)
        r.raise_for_status()
        videos = r.json().get("videos", [])
        if not videos:
            return False
        files = []
        for video in videos:
            for vf in video.get("video_files", []):
                if vf.get("file_type") == "video/mp4" and vf.get("width", 0) >= 640:
                    files.append(vf)
        if not files:
            return False
        chosen = sorted(files, key=lambda x: abs(x.get("width", 0)-1080))[0]
        data = requests.get(chosen["link"], timeout=60)
        data.raise_for_status()
        Path(out_path).write_bytes(data.content)
        return True
    except Exception as e:
        print(f"Pexels fetch skipped for '{query}': {e}")
        return False

def create_thumbnail(text, out_path, width=1280, height=720):
    make_title_card(text, out_path, width, height)

def create_video(scenes, narration, voice_path, out_path, work_dir, video_format, seconds):
    work_dir.mkdir(parents=True, exist_ok=True)
    width, height = (1080, 1920) if video_format == "short" else (1920, 1080)
    count = max(1, len(scenes))
    per_scene = max(3, seconds / count)
    normalized = []

    for i, scene in enumerate(scenes):
        source = work_dir / f"source_{i}.mp4"
        segment = work_dir / f"segment_{i}.mp4"
        query = scene.get("visual_query", "science nature space")
        downloaded = fetch_pexels_clip(query, source)
        if downloaded:
            vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30,setsar=1"
            try:
                run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source),
                     "-t", str(per_scene), "-vf", vf, "-an", "-c:v", "libx264",
                     "-preset", "veryfast", "-pix_fmt", "yuv420p", str(segment)])
            except Exception:
                downloaded = False
        if not downloaded:
            card = work_dir / f"card_{i}.jpg"
            make_title_card(scene.get("caption") or narration[:70], card, width, height)
            run(["ffmpeg", "-y", "-loop", "1", "-i", str(card), "-t", str(per_scene),
                 "-r", "30", "-vf", f"scale={width}:{height},format=yuv420p",
                 "-an", "-c:v", "libx264", "-preset", "veryfast", str(segment)])
        normalized.append(segment)

    concat_file = work_dir / "concat.txt"
    concat_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in normalized), encoding="utf-8")
    silent = work_dir / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(silent)])

    # Simple timed captions, split narration into readable chunks.
    words = narration.split()
    chunks = []
    chunk_size = 8 if video_format == "short" else 11
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))
    duration = max(1, seconds / max(1, len(chunks)))
    def stamp(value):
        ms = int(value * 1000)
        h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    srt = work_dir / "captions.srt"
    lines = []
    for i, chunk in enumerate(chunks):
        start, end = i*duration, min(seconds, (i+1)*duration)
        lines += [str(i+1), f"{stamp(start)} --> {stamp(end)}", chunk, ""]
    srt.write_text("\n".join(lines), encoding="utf-8")

    # Escape path for ffmpeg subtitles filter.
    srt_arg = str(srt.resolve()).replace("\\", "/").replace(":", r"\:")
    vf = f"subtitles='{srt_arg}':force_style='FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=70'"
    run(["ffmpeg", "-y", "-i", str(silent), "-i", str(voice_path),
         "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", "-shortest",
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out_path)])
