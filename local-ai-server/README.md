# Local AI Server

OpenAI-compatible API server that you can customize to call any LLM.

## Quick Start

```bash
cd local-ai-server
pip install -r requirements.txt
python main.py
```

Server runs on `http://localhost:11434` with OpenAI-compatible endpoints:
- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completions

## Customize Your LLM

Edit the `call_your_llm()` function in `main.py` to:

### Option 1: Use a different OpenAI key
```python
import openai
client = openai.OpenAI(api_key="your-different-key")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=temperature,
    max_tokens=max_tokens
)
return response.choices[0].message.content
```

### Option 2: Use Hugging Face
```python
import requests
headers = {"Authorization": f"Bearer {your_hf_token}"}
payload = {"inputs": prompt, "parameters": {"max_length": max_tokens}}
response = requests.post(HF_API_URL, headers=headers, json=payload)
return response.json()[0]["generated_text"]
```

### Option 3: Use Anthropic Claude
```python
import anthropic
client = anthropic.Anthropic(api_key="your-claude-key")
response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=max_tokens,
    messages=[{"role": "user", "content": prompt}]
)
return response.content[0].text
```

### Option 4: Local model with transformers
```python
from transformers import pipeline
generator = pipeline("text-generation", model="your-local-model")
result = generator(prompt, max_length=max_tokens, temperature=temperature)
return result[0]["generated_text"]
```

## Testing

```bash
# List models
curl http://localhost:11434/v1/models

# Test chat completion
curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```
