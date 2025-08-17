import os, asyncio
from playwright.async_api import async_playwright
from ..runners.run_manager import RUN_BUS

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

        # (Optionally) try a generic prefill — unsafe to generalize; keep as demo
        # await page.get_by_label("First name").fill("Anav")
        # await page.get_by_label("Last name").fill("Madan")
        # await page.get_by_label("Email").fill("anav@example.com")

        await RUN_BUS.emit(run_id, '{"type":"done","ts":"","ok":true}')
        await browser.close()
