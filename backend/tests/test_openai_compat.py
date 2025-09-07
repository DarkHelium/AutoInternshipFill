import json


def test_list_models(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "list"
    assert isinstance(data.get("data"), list) and len(data["data"]) >= 1


def test_chat_completions_deepseek_requires_api_key(client):
    # Using a deepseek model should error without DEEPSEEK_API_KEY
    body = {
        "model": "deepseek-reasoner",
        "messages": [{"role": "user", "content": "Say hi"}],
    }
    r = client.post("/v1/chat/completions", json=body)
    assert r.status_code == 500
    assert "DEEPSEEK_API_KEY" in r.text


def test_chat_completions_forward_success_with_mock(client, monkeypatch):
    # Mock httpx.AsyncClient used in routes_openai_compat to avoid network
    from app.api import routes_openai_compat as roc  # type: ignore

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "Hello from mock"}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            return FakeResponse()

    monkeypatch.setattr(roc.httpx, "AsyncClient", FakeAsyncClient)

    body = {
        "model": "gpt-4.1",
        "messages": [{"role": "user", "content": "Say hi"}],
        "temperature": 0.1,
        "max_tokens": 10,
    }
    r = client.post("/v1/chat/completions", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["message"]["content"] == "Hello from mock"

