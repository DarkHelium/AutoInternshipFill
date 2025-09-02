"""
OpenAI-compatible endpoints served by the main backend app.
Provides /v1/models and /v1/chat/completions compatible with OpenAI.
Routes to DeepSeek or any OpenAI-compatible base URL.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import time
import uuid
import httpx

router = APIRouter(prefix="/v1", tags=["openai-compat"]) 


# Request/Response Models (OpenAI-compatible)
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4000
    stream: Optional[bool] = False


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "local"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]


# Env configuration
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_FORWARD_BASE_URL = os.getenv("OPENAI_FORWARD_BASE_URL") or os.getenv("OPENAI_BASE_URL", "http://host.docker.internal:11434/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# Available models (present a unified list; you can customize)
def _available_models():
    now = int(time.time())
    return [
        {"id": os.getenv("DEFAULT_AI_MODEL", "gpt-5"), "created": now},
        {"id": "deepseek-reasoner", "created": now},
        {"id": "gpt-4.1", "created": now},
        {"id": "gpt-4o", "created": now},
    ]


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    models = [ModelInfo(id=m["id"], created=m["created"]) for m in _available_models()]
    return ModelsResponse(data=models)


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    if not request.messages:
        raise HTTPException(400, "messages required")

    # Extract last user message for usage estimation
    user_message = next((m.content for m in reversed(request.messages) if m.role == "user"), "")

    response_content = await _call_llm(
        messages=request.messages,
        model=request.model,
        temperature=request.temperature or 0.7,
        max_tokens=request.max_tokens or 4000,
    )

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    choice = ChatCompletionChoice(
        index=0,
        message=ChatMessage(role="assistant", content=response_content),
        finish_reason="stop",
    )

    # Rough usage estimate
    prompt_tokens = int(len(user_message.split()) * 1.3)
    completion_tokens = int(len(response_content.split()) * 1.3)
    usage = ChatCompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return ChatCompletionResponse(
        id=completion_id,
        created=int(time.time()),
        model=request.model,
        choices=[choice],
        usage=usage,
    )


async def _call_llm(*, messages: List[ChatMessage], model: str, temperature: float, max_tokens: int) -> str:
    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # DeepSeek route
    if "deepseek" in model.lower():
        if not DEEPSEEK_API_KEY:
            raise HTTPException(500, "DEEPSEEK_API_KEY not configured")
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{DEEPSEEK_BASE_URL}/v1/chat/completions", json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)
        data = resp.json()
        return data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get("reasoning_content", "")

    # Forward to OpenAI-compatible base (e.g., local server)
    headers = {"Content-Type": "application/json"}
    if OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OPENAI_FORWARD_BASE_URL}/chat/completions", json=payload, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)
    data = resp.json()
    return data["choices"][0]["message"]["content"]

