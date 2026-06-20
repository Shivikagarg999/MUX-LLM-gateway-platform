from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import cache, router
from app.auth import verify_api_key
from app.db import init_db
from app.metering import get_stats, log_request
from app.models import ChatCompletionRequest
from app.rate_limit import check_rate_limit

load_dotenv()

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mux", description="A multi-provider LLM gateway", lifespan=lifespan)


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/stats")
async def stats(api_key: dict = Depends(verify_api_key)):
    return get_stats(api_key["id"])


@app.post("/v1/chat/completions")
async def chat_completions(payload: ChatCompletionRequest, api_key: dict = Depends(verify_api_key)):
    if not check_rate_limit(api_key["id"], api_key["rate_limit_per_minute"]):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for this API key")

    body = payload.model_dump(exclude_none=True)

    prompt_text = cache.extract_prompt(body["messages"])
    embedding = cache.embed(prompt_text) if prompt_text else None

    if embedding is not None:
        cached = cache.find_similar(embedding)
        if cached is not None:
            result = cached["response"]
            result["mux_cache"] = "hit"
            log_request(api_key["id"], result.get("mux_provider"), True, result.get("usage"))
            return result

    try:
        result = await router.route(body)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.json())

    result["mux_cache"] = "miss"

    if embedding is not None:
        cache.store(prompt_text, embedding, result)

    log_request(api_key["id"], result.get("mux_provider"), False, result.get("usage"))

    return result
