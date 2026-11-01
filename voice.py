import asyncio, edge_tts
from pathlib import Path

def generate_voice(text: str, out_path: Path, voice: str):
    async def _make():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_path))
    asyncio.run(_make())
