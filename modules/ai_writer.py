import os
import re
import json
import time
import random
import httpx

from google import genai


def _extract_json(text: str) -> dict:
    text = text.strip()

    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start < 0 or end < start:
        raise ValueError("Gemini did not return a JSON object.")

    return json.loads(text[start:end + 1])


def _is_temporary_error(error):
    message = str(error).lower()

    temporary_terms = [
        "503",
        "unavailable",
        "high demand",
        "429",
        "resource_exhausted",
        "500",
        "502",
        "504",
        "internal server error",
        "deadline exceeded",
        "temporarily",
        "remoteprotocolerror",
        "server disconnected",
        "connection reset",
        "connection error",
        "readtimeout",
        "connecttimeout",
        "timed out"
    ]

    if isinstance(error, httpx.TransportError):
        return True

    return any(term in message for term in temporary_terms)


def _generate_with_retry(client, model, prompt, attempts=5):

    last_error = None

    for attempt in range(1, attempts + 1):

        try:
            print(
                f"Gemini request attempt {attempt}/{attempts}"
            )

            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            if not response or not response.text:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            return response.text

        except Exception as error:

            last_error = error

            print(
                f"Gemini request failed: "
                f"{type(error).__name__}: {error}"
            )

            if not _is_temporary_error(error):
                raise

            if attempt == attempts:
                break

            delay = min(
                60,
                (2 ** attempt) * 5 + random.uniform(0, 3)
            )

            print(
                f"Temporary connection/API error. "
                f"Retrying in {delay:.1f} seconds."
            )

            time.sleep(delay)

    raise RuntimeError(
        f"Gemini failed after {attempts} attempts. "
        f"Last error: {last_error}"
    ) from last_error


def generate_video(config: dict, video_format: str, research: dict) -> dict:

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY GitHub secret."
        )

    client = genai.Client(
        api_key=api_key,
        http_options={
            "timeout": 120000,
            "retry_options": {
                "attempts": 1
            }
        }
    )

    duration = (
        config["short_seconds"]
        if video_format == "short"
        else config["long_seconds"]
    )

    scene_count = (
        config["short_scene_count"]
        if video_format == "short"
        else config["long_scene_count"]
    )

    word_target = (
        100 if video_format == "short" else 390
    )

    prompt = f"""
You are an accurate and engaging YouTube writer
for a United States audience.

Channel: {config['channel_category']}
Subtopics: {', '.join(config['subtopics'])}

Format: {video_format}
Target duration: approximately {duration} seconds.
Target narration: approximately {word_target} words.

Write natural American English.

Use a strong truthful opening hook,
clear explanations, and a satisfying ending.

Make the script original.
Do not invent statistics, quotations, or source URLs.
Avoid unsupported claims and misinformation.
Do not copy source wording.

Research topic: {research.get('title', '')}
Research URL: {research.get('url', '')}

Research extract:
{research.get('extract', '')[:6500]}

Return ONLY valid JSON in this exact structure:

{{
 "topic": "specific topic",
 "title": "engaging title, maximum 95 characters",
 "description": "YouTube description",
 "tags": ["tag1", "tag2"],
 "thumbnail_text": "2 to 5 short words",
 "narration": "complete spoken narration",
 "scenes": [
   {{
     "visual_query": "specific stock footage search phrase",
     "caption": "short on-screen phrase"
   }}
 ],
 "sources": []
}}

Create exactly {scene_count} scene objects.

Make every visual_query specific and visually different
from the other scenes.

Ensure narration is one continuous coherent script.
"""

    model = config.get(
        "gemini_model",
        "gemini-2.5-flash"
    )

    response_text = _generate_with_retry(
        client,
        model,
        prompt,
        attempts=5
    )

    data = _extract_json(response_text)

    required = [
        "topic",
        "title",
        "description",
        "tags",
        "thumbnail_text",
        "narration",
        "scenes"
    ]

    for key in required:
        if key not in data:
            raise ValueError(
                f"AI response missing required field: {key}"
            )

    if not isinstance(data["scenes"], list):
        raise ValueError("Invalid scenes returned by Gemini.")

    if not data["scenes"]:
        raise ValueError("Gemini returned no scenes.")

    if len(data["scenes"]) != scene_count:
        raise ValueError(
            f"Expected {scene_count} scenes, "
            f"received {len(data['scenes'])}."
        )

    if not isinstance(data["tags"], list):
        raise ValueError("Gemini returned invalid tags.")

    data["title"] = str(data["title"])[:95]

    data["tags"] = [
        str(tag)[:30]
        for tag in data["tags"][:config.get("max_tags", 15)]
    ]

    data["narration"] = str(data["narration"])
    data["description"] = str(data["description"])
    data["thumbnail_text"] = str(data["thumbnail_text"])

    print("Gemini script generated successfully.")

    return data
