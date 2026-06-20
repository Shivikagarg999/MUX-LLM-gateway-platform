import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app import router
from app.models import ChatCompletionRequest

load_dotenv()

app = FastAPI(title="Mux", description="A multi-provider LLM gateway")


@app.get("/")
def root():
    return {"service": "mux", "status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(payload: ChatCompletionRequest):
    body = payload.model_dump(exclude_none=True)

    try:
        return await router.route(body)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.json())
