import os, asyncio
from playwright.async_api import async_playwright
from ..runners.run_manager import RUN_BUS, gate_for
from ..ats_fillers import prefill_application, ApplicantAnswers
from ..auth_orchestrator import ensure_authenticated

async def greenhouse_prefill_headed(run_id: str, apply_url: str, files_dir: str):
    """Run browser in headed mode with VNC display for manual review"""
    DISPLAY = os.environ.get("DISPLAY", ":20")
    
    await RUN_BUS.emit(run_id, '{"type":"log","ts":"","level":"info","message":"Launching headed browser in VNC..."}')
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, 
            args=["--force-device-scale-factor=1"]
        )
        
        # Handle authentication first (login walls, guest options, etc.)
        page = await ensure_authenticated(browser, apply_url, run_id)
        await RUN_BUS.emit(run_id, f'{{"type":"log","level":"info","message":"Authentication complete, proceeding with form fill"}}')

        # Try to snapshot
        os.makedirs(files_dir, exist_ok=True)
        screenshot_path = os.path.join(files_dir, f"{run_id}.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        await RUN_BUS.emit(run_id, f'{{"type":"screenshot","ts":"","url":"/files/{os.path.basename(screenshot_path)}"}}')

        # Use comprehensive ATS filler system
        applicant = ApplicantAnswers(
            full_name="Anav Madan",
            email="anav.madan@gmail.com",
            phone="408-824-0866",
            city="Fremont",
            state="CA",
            linkedin="https://www.linkedin.com/in/anav-madan-03a9a0301/",
            github="https://github.com/DarkHelium",
            us_citizen=True,
            needs_sponsorship_now_or_future=False,
            protected_veteran=False,
            has_disability=False,
        )

        # Find tailored resume PDF
        resume_path = None
        try:
            # Try to find resume by job ID
            job_id = run_id.split('_')[0] if '_' in run_id else run_id
            resume_path = os.path.join(files_dir, f"resume_tailored_{job_id}.pdf")
            if not os.path.exists(resume_path):
                resume_path = None
        except Exception:
            resume_path = None

        # Run comprehensive ATS prefill
        try:
            await prefill_application(
                page=page,
                apply_url=apply_url,
                resume_path=resume_path,
                applicant=applicant,
                run_id=run_id,
            )
        except Exception as e:
            await RUN_BUS.emit(run_id, f'{{"type":"log","level":"warn","message":"ATS prefill error: {str(e)}"}}')

        # Wait for manual review and approval
        await RUN_BUS.emit(run_id, '{"type":"gate","prompt":"Review in the VNC window then click Apply. When done, hit Mark Submitted."}')
        await gate_for(run_id).wait()
        
        # After approval, capture final state
        final_screenshot = os.path.join(files_dir, f"{run_id}_final.png")
        await page.screenshot(path=final_screenshot, full_page=True)
        await RUN_BUS.emit(run_id, f'{{"type":"screenshot","ts":"","url":"/files/{os.path.basename(final_screenshot)}"}}')
        
        await RUN_BUS.emit(run_id, '{"type":"done","ts":"","ok":true}')
        await browser.close()

# Keep original headless version for backward compatibility
async def greenhouse_prefill(run_id: str, apply_url: str, files_dir: str):
    await RUN_BUS.emit(run_id, '{"type":"log","ts":"","level":"info","message":"Launching browser..."}')
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(apply_url, wait_until="domcontentloaded")
        await RUN_BUS.emit(run_id, f'{{"type":"log","level":"info","message":"Opened {apply_url}"}}')

        # Try to snapshot
        os.makedirs(files_dir, exist_ok=True)
        screenshot_path = os.path.join(files_dir, f"{run_id}.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        await RUN_BUS.emit(run_id, f'{{"type":"screenshot","ts":"","url":"/files/{os.path.basename(screenshot_path)}"}}')

        await RUN_BUS.emit(run_id, '{"type":"done","ts":"","ok":true}')
        await browser.close()
