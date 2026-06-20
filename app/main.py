import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app.models import ChatCompletionRequest
from app.providers import groq_provider

load_dotenv()

app = FastAPI(title="Mux", description="A multi-provider LLM gateway")


@app.get("/")
def root():
    return {"service": "mux", "status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(payload: ChatCompletionRequest):
    body = payload.model_dump(exclude_none=True)

    try:
        return await groq_provider.complete(body)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.json())
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Groq unreachable: {exc}")
