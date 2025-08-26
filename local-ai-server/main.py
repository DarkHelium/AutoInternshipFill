"""
Local AI Server - OpenAI-compatible API using FastAPI
Acts as a drop-in replacement for OpenAI API
"""
import json
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid

app = FastAPI(title="Local AI Server", description="OpenAI-compatible API for local LLMs")

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

# Available models
AVAILABLE_MODELS = [
    {"id": "gpt-4.1", "created": int(time.time())},
    {"id": "gpt-5", "created": int(time.time())},
    {"id": "gpt-4o", "created": int(time.time())},
]

@app.get("/")
async def root():
    return {"message": "Local AI Server - OpenAI Compatible API", "status": "running"}

@app.get("/v1/models")
async def list_models() -> ModelsResponse:
    """List available models (OpenAI compatible)"""
    models = [
        ModelInfo(id=model["id"], created=model["created"])
        for model in AVAILABLE_MODELS
    ]
    return ModelsResponse(data=models)

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """Create chat completion (OpenAI compatible)"""
    try:
        # Extract the user's prompt
        user_message = None
        for msg in request.messages:
            if msg.role == "user":
                user_message = msg.content
                break
        
        if not user_message:
            raise HTTPException(400, "No user message found")
        
        # Call your LLM here - replace this with your actual LLM call
        response_content = await call_your_llm(
            prompt=user_message,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Create OpenAI-compatible response
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        
        choice = ChatCompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=response_content),
            finish_reason="stop"
        )
        
        # Estimate token usage (replace with actual counting if available)
        prompt_tokens = len(user_message.split()) * 1.3  # Rough estimate
        completion_tokens = len(response_content.split()) * 1.3
        
        usage = ChatCompletionUsage(
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            total_tokens=int(prompt_tokens + completion_tokens)
        )
        
        return ChatCompletionResponse(
            id=completion_id,
            created=int(time.time()),
            model=request.model,
            choices=[choice],
            usage=usage
        )
        
    except Exception as e:
        raise HTTPException(500, f"LLM call failed: {str(e)}")

async def call_your_llm(prompt: str, model: str, temperature: float, max_tokens: int) -> str:
    """
    Replace this function with your actual LLM call
    This could be:
    - OpenAI API call to a different endpoint
    - Hugging Face API
    - Local model inference
    - Anthropic Claude
    - etc.
    """
    
    # EXAMPLE 1: Call OpenAI with a different API key
    # import openai
    # client = openai.OpenAI(api_key="your-different-key")
    # response = client.chat.completions.create(
    #     model="gpt-4",
    #     messages=[{"role": "user", "content": prompt}],
    #     temperature=temperature,
    #     max_tokens=max_tokens
    # )
    # return response.choices[0].message.content
    
    # EXAMPLE 2: Call Hugging Face
    # import requests
    # headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    # payload = {"inputs": prompt, "parameters": {"max_length": max_tokens}}
    # response = requests.post(HF_URL, headers=headers, json=payload)
    # return response.json()[0]["generated_text"]
    
    # EXAMPLE 3: Mock response for testing
    if "json" in prompt.lower():
        return '''
        {
            "key_requirements": [
                "5+ years software engineering experience",
                "Python, FastAPI, React expertise",
                "Database design and optimization",
                "API development and integration",
                "Agile development methodology"
            ],
            "salary_range": "$120,000 - $160,000",
            "remote_policy": "hybrid",
            "difficulty_score": 0.7,
            "match_score": 0.8,
            "missing_skills": [
                "Advanced Docker/Kubernetes"
            ],
            "competitive_advantages": [
                "Strong API development background",
                "Full-stack capabilities"
            ],
            "improvement_suggestions": [
                "Highlight specific API projects",
                "Mention scalability achievements",
                "Include database optimization examples"
            ],
            "ats_keywords": [
                "software engineer", "python", "fastapi", "react", "apis", "database"
            ],
            "company_insights": "Technology-focused company seeking experienced full-stack engineers"
        }
        '''
    
    # Simple text response
    return f"This is a mock response from the local AI server for model {model}. In a real implementation, you would call your preferred LLM here."

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=11434)
