def test_get_default_profile_creates_and_returns_default(client):
    r = client.get("/profiles/default")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "default"
    # Basic keys present
    assert "name" in data and "email" in data


def test_update_default_profile(client):
    body = {
        "name": "Alice",
        "email": "alice@example.com",
        "skills": ["Python", "FastAPI"],
    }
    r = client.put("/profiles/default", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert data["skills"] == ["Python", "FastAPI"]

