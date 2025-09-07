import sys
import types


WAYMO_URL = (
    "https://careers.withwaymo.com/jobs/2026-summer-intern-bs-ms-systems-engineering-applied-genai-"
    "mountain-view-california-united-states?fbclid=PAdGRleAMoC4BleHRuA2FlbQIxMQABp944-ct0dQ8WZggxYvTNWr0XlRGii1FWxZcGnx8dihrOMCQTMXjpP-lDrFxc_aem_wp3HM_Ix8cBrfz7yv_TwPg"
)


class CaptureAIService:
    def __init__(self):
        self.last_job_description = None

    async def analyze_job_description(self, job_url, job_description, user_profile):
        # Capture for assertions
        self.last_job_description = job_description
        # Return deterministic analysis
        return {
            "key_requirements": ["python", "systems", "ml"],
            "salary_range": None,
            "remote_policy": None,
            "difficulty_score": 0.6,
            "match_score": 0.55,
            "improvement_suggestions": ["Highlight systems projects"],
        }

    async def tailor_resume(self, job_analysis, base_resume, user_constraints):
        return {
            "tailored_resume": {"name": "Test"},
            "changes_explanation": "Reordered bullets",
            "ats_score": 0.8,
            "keyword_integration": ["python", "systems"],
        }


def _force_httpx_fallback():
    """Make playwright scraping raise so the code uses httpx fallback."""
    fake_mod = types.ModuleType("app.playwright_service")

    async def enhanced_job_scraping(url: str):
        raise RuntimeError("force fallback to httpx")

    fake_mod.enhanced_job_scraping = enhanced_job_scraping
    sys.modules["app.playwright_service"] = fake_mod


def test_fetch_waymo_job_description(client, monkeypatch):
    # Arrange AI service and force fallback to httpx
    from app import main as app_main  # type: ignore

    ai = CaptureAIService()
    monkeypatch.setattr(app_main, "get_ai_service", lambda user_api_key=None, model=None: ai)
    _force_httpx_fallback()

    # Mock httpx.AsyncClient used in app.main to avoid real network
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            html = """
            <html><main>
                <h1>Waymo Systems Engineering Intern</h1>
                <p>We use Python, ML, distributed systems, applied GenAI.</p>
            </main></html>
            """
            return FakeResponse(html)

    import httpx  # type: ignore
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    # Act: analyze the job URL (this should fetch via httpx and parse)
    r = client.post("/ai/analyze-job", json={"job_url": WAYMO_URL})
    assert r.status_code == 200
    data = r.json()
    # Assert AI response from our fake and that we captured a non-empty JD
    assert data["key_requirements"] == ["python", "systems", "ml"]
    assert isinstance(ai.last_job_description, str) and len(ai.last_job_description) > 50


def test_tailor_resume_after_waymo_analysis(client, monkeypatch):
    # Arrange AI service and fallback
    from app import main as app_main  # type: ignore

    ai = CaptureAIService()
    monkeypatch.setattr(app_main, "get_ai_service", lambda user_api_key=None, model=None: ai)
    _force_httpx_fallback()

    # Mock httpx.AsyncClient used in app.main to avoid real network
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            html = """
            <html><main>
                <h1>Waymo Systems Engineering Intern</h1>
                <p>We use Python, ML, distributed systems, applied GenAI.</p>
            </main></html>
            """
            return FakeResponse(html)

    import httpx  # type: ignore
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    # Ensure default profile exists and base resume is set
    client.put("/profiles/default", json={"name": "Waymo Tester", "email": "tester@example.com"})
    client.put("/profile/base-resume", json={"url": "http://localhost/files/base.pdf"})

    # First analyze to create a job record
    analyze = client.post("/ai/analyze-job", json={"job_url": WAYMO_URL})
    assert analyze.status_code == 200
    job_id = analyze.json()["job_id"]

    # Then tailor resume for that job
    tailor = client.post("/ai/tailor-resume", json={"job_id": job_id})
    assert tailor.status_code == 200
    payload = tailor.json()
    assert payload["ats_score"] == 0.8
    assert payload["keyword_integration"] == ["python", "systems"]
