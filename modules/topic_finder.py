import os, json
from google import genai

def choose_topic(config: dict) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY.")
    client = genai.Client(api_key=key)
    prompt = f"""
Choose ONE specific, evergreen, interesting video topic for a United States
Facts & Knowledge YouTube channel.
Allowed areas: {', '.join(config['subtopics'])}.
Avoid topics recently overused in generic fact videos, current breaking news,
medical diagnosis/treatment, politics, dangerous stunts, and claims needing
highly specialized sourcing. Return only the topic phrase, no explanation.
"""
    result = client.models.generate_content(
        model=config.get("gemini_model", "gemini-2.5-flash"),
        contents=prompt
    )
    topic = (result.text or "").strip().strip('"')
    if not topic:
        raise RuntimeError("AI did not return a topic.")
    return topic[:160]
