import os

import httpx

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


async def complete(payload: dict) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )

    response.raise_for_status()
    return response.json()
