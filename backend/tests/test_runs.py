import sys
import types


def test_create_run_and_payload(client):
    # Stub out heavy Playwright scraping to avoid external dependencies
    fake_mod = types.ModuleType("app.playwright_service")

    async def fake_enhanced_job_scraping(url: str):
        return {}

    fake_mod.enhanced_job_scraping = fake_enhanced_job_scraping
    sys.modules["app.playwright_service"] = fake_mod

    # Create a run
    create_resp = client.post("/runs", json={"job_url": "https://example.com/job"})
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["status"] == "created"
    assert created["job_url"] == "https://example.com/job"
    run_id = created["id"]

    # Fetch payload for the run
    payload_resp = client.get(f"/runs/{run_id}/payload")
    assert payload_resp.status_code == 200
    payload = payload_resp.json()
    assert "tailored_resume" in payload
    tr = payload["tailored_resume"]
    # Ensure minimal expected structure
    assert "contact" in tr and "skills" in tr

