import sys
import types


class FakeAIService:
    async def tailor_resume(self, job_analysis, base_resume, user_constraints):
        # Return a deterministic mocked tailoring result
        return {
            "tailored_resume": {"name": "Alice", "sections": ["Experience", "Education"]},
            "changes_explanation": "Added keywords and restructured bullets",
            "ats_score": 0.87,
            "keyword_integration": ["python", "fastapi", "docker"],
            "improvement_suggestions": ["Quantify achievements", "Add project links"],
        }

    async def generate_ats_preview(self, tailored_resume):
        return {"ats_summary": "Looks good", "score": 0.9}


def _stub_playwright_module():
    """Avoid importing real Playwright in create_run path."""
    fake_mod = types.ModuleType("app.playwright_service")

    async def fake_enhanced_job_scraping(url: str):
        return {}

    fake_mod.enhanced_job_scraping = fake_enhanced_job_scraping
    sys.modules["app.playwright_service"] = fake_mod


def test_tailor_resume_happy_path(client, monkeypatch):
    # Patch AI service used inside app.main
    from app import main as app_main  # type: ignore

    monkeypatch.setattr(app_main, "get_ai_service", lambda user_api_key=None, model=None: FakeAIService())
    _stub_playwright_module()

    # Ensure default profile exists and then set base resume URL
    resp = client.put("/profiles/default", json={"name": "Alice", "email": "alice@example.com"})
    assert resp.status_code == 200
    # Set base resume via dedicated endpoint
    resp = client.put("/profile/base-resume", json={"url": "http://localhost/files/base.pdf"})
    assert resp.status_code == 200

    # Create a job by creating a run, capture job_id
    create_run = client.post("/runs", json={"job_url": "https://example.com/job/123"})
    assert create_run.status_code == 200
    job_id = create_run.json()["job_id"]

    # Tailor the resume for that job
    tailor = client.post("/ai/tailor-resume", json={"job_id": job_id})
    assert tailor.status_code == 200
    data = tailor.json()
    assert data["changes_explanation"]
    assert data["ats_score"] == 0.87
    assert data["keyword_integration"] == ["python", "fastapi", "docker"]
    assert data["tailored_resume"]["name"] == "Alice"

    # Latest tailor result should exist and job should be marked tailored
    latest = client.get(f"/jobs/{job_id}/tailor/latest")
    assert latest.status_code == 200
    latest_data = latest.json()
    assert latest_data is not None
    assert latest_data["keywords"] == ["python", "fastapi", "docker"]

    job = client.get(f"/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "tailored"


def test_tailor_resume_requires_base_resume(client, monkeypatch):
    from app import main as app_main  # type: ignore

    monkeypatch.setattr(app_main, "get_ai_service", lambda user_api_key=None, model=None: FakeAIService())
    _stub_playwright_module()

    # Create job via run
    create_run = client.post("/runs", json={"job_url": "https://example.com/job/abc"})
    assert create_run.status_code == 200
    job_id = create_run.json()["job_id"]

    # Do not set base resume URL; endpoint should reject
    tailor = client.post("/ai/tailor-resume", json={"job_id": job_id})
    assert tailor.status_code == 400
    assert "upload a base resume" in tailor.text.lower()


def test_ats_preview_after_tailor(client, monkeypatch):
    from app import main as app_main  # type: ignore

    monkeypatch.setattr(app_main, "get_ai_service", lambda user_api_key=None, model=None: FakeAIService())
    _stub_playwright_module()

    # Set base resume
    client.put("/profiles/default", json={"name": "Bob", "email": "bob@example.com"})
    client.put("/profile/base-resume", json={"url": "http://localhost/files/base.pdf"})

    # Create job
    create_run = client.post("/runs", json={"job_url": "https://example.com/job/xyz"})
    job_id = create_run.json()["job_id"]

    # Tailor first
    assert client.post("/ai/tailor-resume", json={"job_id": job_id}).status_code == 200

    # Then request ATS preview
    preview = client.post("/ai/ats-preview", params={"job_id": job_id})
    assert preview.status_code == 200
    data = preview.json()
    assert data["ats_summary"] == "Looks good"
    assert data["score"] == 0.9


def test_tailor_resume_job_not_found(client, monkeypatch):
    from app import main as app_main  # type: ignore

    monkeypatch.setattr(app_main, "get_ai_service", lambda user_api_key=None, model=None: FakeAIService())
    # Missing job should yield 404
    r = client.post("/ai/tailor-resume", json={"job_id": "non-existent"})
    assert r.status_code == 404
