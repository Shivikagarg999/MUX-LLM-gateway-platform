import logging

import httpx

from app.providers import gemini_provider, groq_provider

logger = logging.getLogger("mux.router")

PROVIDER_CHAIN = [
    ("groq", groq_provider),
    ("gemini", gemini_provider),
]

async def route(payload: dict) -> dict:
    last_error = None

    for name, provider in PROVIDER_CHAIN:
        try:
            result = await provider.complete(payload)
            result["mux_provider"] = name
            return result
        except RuntimeError as exc:
            logger.warning("Skipping %s: %s", name, exc)
            last_error = exc
        except httpx.HTTPStatusError as exc:
            logger.warning("%s returned %s, falling back", name, exc.response.status_code)
            last_error = exc
        except httpx.RequestError as exc:
            logger.warning("%s unreachable: %s, falling back", name, exc)
            last_error = exc

    raise RuntimeError(f"All providers failed. Last error: {last_error}")
