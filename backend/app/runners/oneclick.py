import asyncio, json, os, re
from typing import Optional

from playwright.async_api import async_playwright

from ..runners.run_manager import RUN_BUS, gate_for
from ..auth_orchestrator import ensure_authenticated
from ..ats_fillers import prefill_application, ApplicantAnswers


CHATGPT_URL = os.getenv("CHATGPT_URL", "https://chatgpt.com/")


def _extract_json_blocks(text: str) -> Optional[dict]:
    # Try to pull the first JSON object containing keys we care about
    # Commonly ChatGPT wraps in ```json ... ```
    fence = re.search(r"```json\s*([\s\S]*?)```", text, re.I)
    blob = fence.group(1) if fence else text
    m = re.search(r"\{[\s\S]*\}", blob)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        if isinstance(data, dict) and ("resume" in data or "keywords" in data):
            # normalize
            return {
                "keywords": data.get("keywords", []),
                "resume": data.get("resume", data),
            }
    except Exception:
        return None
    return None


async def oneclick_tailor_apply(
    run_id: str,
    job_title: str,
    apply_url: str,
    jd_text: str,
    files_dir: str,
):
    await RUN_BUS.emit(run_id, json.dumps({"type": "log", "level": "info", "message": "Starting one-click tailor+apply"}))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        # 1) ChatGPT — ensure login, send prompt, capture JSON
        page = await ensure_authenticated(browser, CHATGPT_URL, run_id)
        await page.wait_for_load_state("domcontentloaded")

        prompt = (
            "You are an expert ATS resume editor. Return strict JSON object with keys: "
            "keywords: string[], resume: {...}. Use this job description (JD) below. "
            "Output only JSON in a code block. JD:\n" + jd_text
        )

        # Focus composer and send prompt
        try:
            # Try desktop textarea
            ta = page.locator("textarea").nth(0)
            await ta.click()
            await ta.fill("")
            await ta.type(prompt)
            await ta.press("Enter")
            await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"info","message":"Prompt sent to ChatGPT"}))
        except Exception as e:
            await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"warn","message":f"ChatGPT composer not found: {e}"}))

        # Wait and scrape last assistant message
        await page.wait_for_timeout(5000)
        content = ""
        try:
            last = page.locator(".markdown, .prose").last
            content = await last.inner_text()
        except Exception:
            pass

        data = _extract_json_blocks(content)
        if not data:
            await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"warn","message":"Could not parse JSON from ChatGPT; pausing for manual fix"}))
            await RUN_BUS.emit(run_id, json.dumps({"type":"gate","prompt":"Paste structured JSON in the right panel and click Render PDF, then click Start Apply from Jobs."}))
            return

        # 2) Render tailored PDF artifact on server (emit for UX only)
        await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"info","message":"Got JSON; backend will render PDF"}))

        # 3) Navigate to application URL and prefill
        page2 = await browser.new_page(viewport={"width": 1280, "height": 860})
        await page2.goto(apply_url, wait_until="domcontentloaded")
        await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"info","message":f"Opened {apply_url}"}))

        # Save first screenshot
        os.makedirs(files_dir, exist_ok=True)
        shot = os.path.join(files_dir, f"{run_id}_open.png")
        await page2.screenshot(path=shot, full_page=True)
        await RUN_BUS.emit(run_id, json.dumps({"type":"screenshot","ts":"","url":f"/files/{os.path.basename(shot)}"}))

        # Applicant placeholder (could read from Profile later)
        applicant = ApplicantAnswers(
            full_name=os.getenv("APPLICANT_NAME", "Your Name"),
            email=os.getenv("APPLICANT_EMAIL", "me@example.com"),
            phone=os.getenv("APPLICANT_PHONE", "555-555-5555"),
            city=os.getenv("APPLICANT_CITY", "San Jose"),
            state=os.getenv("APPLICANT_STATE", "CA"),
            linkedin=os.getenv("APPLICANT_LINKEDIN", ""),
            github=os.getenv("APPLICANT_GITHUB", ""),
            us_citizen=True,
            needs_sponsorship_now_or_future=False,
            protected_veteran=False,
            has_disability=False,
        )

        resume_path = None  # optional, if a tailored PDF exists

        try:
            await prefill_application(
                page=page2,
                apply_url=apply_url,
                resume_path=resume_path,
                applicant=applicant,
                run_id=run_id,
            )
        except Exception as e:
            await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"warn","message":f"ATS prefill error: {e}"}))

        await RUN_BUS.emit(run_id, json.dumps({"type":"gate","prompt":"Review and submit the application in the desktop window, then click Mark Submitted."}))
        await gate_for(run_id).wait()

        final = os.path.join(files_dir, f"{run_id}_final.png")
        await page2.screenshot(path=final, full_page=True)
        await RUN_BUS.emit(run_id, json.dumps({"type":"screenshot","ts":"","url":f"/files/{os.path.basename(final)}"}))
        await RUN_BUS.emit(run_id, json.dumps({"type":"done","ok":True}))


