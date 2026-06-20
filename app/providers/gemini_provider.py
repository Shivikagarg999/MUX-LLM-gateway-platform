import os

import httpx

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-2.5-flash"


async def complete(payload: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    gemini_payload = {**payload, "model": DEFAULT_MODEL}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{GEMINI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=gemini_payload,
        )

    response.raise_for_status()
    return response.json()
