import json
import os
import re
import time
import random

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


def _generate_with_retry(client, model, prompt, attempts=5):
    last_error = None

    for attempt in range(attempts):
        try:
            print(f"Gemini request: attempt {attempt + 1}/{attempts}")

            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            if not response.text:
                raise ValueError("Gemini returned an empty response.")

            return response.text

        except Exception as error:
            last_error = error
            error_text = str(error).lower()

            temporary_error = any(term in error_text for term in [
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
                "temporarily"
            ])

            if not temporary_error or attempt == attempts - 1:
                raise

            delay = min(60, (2 ** (attempt + 1)) + random.uniform(0, 2))

            print(
                f"Gemini temporarily unavailable. "
                f"Retrying in {delay:.1f} seconds..."
            )

            time.sleep(delay)

    raise RuntimeError("Gemini failed after retries.") from last_error


def generate_video(config: dict, video_format: str, research: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY secret.")

    client = genai.Client(api_key=api_key)

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

    word_target = 100 if video_format == "short" else 390

    prompt = f"""
You are an accurate, engaging YouTube writer for a United States audience.

Channel: {config['channel_category']}
Subtopics: {', '.join(config['subtopics'])}

Format: {video_format}
Target duration: about {duration} seconds.
Aim for about {word_target} spoken words.

Write in natural American English.
Use a strong but truthful opening hook, clear explanations,
and a satisfying ending.

Make the script original.
Do not copy source wording.
Avoid fabricated statistics, fake quotations,
sensational misinformation, medical advice,
or unsupported claims.

Use the research extract as a starting point,
not as proof of every claim.

If a claim cannot be supported by the research,
omit it or clearly qualify it.

Do not invent citations or source URLs.
Include the supplied research URL as a reference
only if it exists.

Add a short "Sources to check" list for additional
references you genuinely know.

Do not add copyrighted lyrics or imitate a living creator's style.

Research topic: {research.get('title', '')}
Research URL: {research.get('url', '')}

Research extract:
{research.get('extract', '')[:6500]}

Return ONLY valid JSON with this exact shape:

{{
 "topic": "specific topic",
 "title": "engaging title, max 95 characters",
 "description": "useful YouTube description with a brief source note",
 "tags": ["tag1", "tag2"],
 "thumbnail_text": "2 to 5 short words",
 "narration": "complete spoken narration",
 "scenes": [
   {{
     "visual_query": "short stock-footage search phrase",
     "caption": "short on-screen phrase"
   }}
 ],
 "sources": ["URLs supplied in research or genuinely known references"]
}}

Create exactly {scene_count} scene objects.
Ensure narration is one continuous coherent script.
"""

    model = config.get("gemini_model", "gemini-2.5-flash")

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
            raise ValueError(f"AI response missing required field: {key}")

    if not isinstance(data["scenes"], list) or not data["scenes"]:
        raise ValueError("AI returned no scenes.")

    if not isinstance(data["tags"], list):
        raise ValueError("AI returned invalid tags.")

    if len(data["scenes"]) != scene_count:
        raise ValueError(
            f"Expected {scene_count} scenes, "
            f"but Gemini returned {len(data['scenes'])}."
        )

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
