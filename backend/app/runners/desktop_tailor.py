import os, asyncio, httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from ..runners.run_manager import RUN_BUS

async def scrape_jd(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(url)
        soup = BeautifulSoup(r.text, "lxml")
        cont = soup.select_one("main, .content, #content, .job, article") or soup
        txt = cont.get_text(" ", strip=True)
        return " ".join(txt.split())[:120000]
    except Exception:
        return ""

async def desktop_tailor_run(run_id: str, job_url: str):
    await RUN_BUS.emit(run_id, '{"type":"log","level":"info","message":"Launching desktop for tailoring..."}')
    jd_text = await scrape_jd(job_url)
    # send JD text to UI (they'll get a "Copy JD" button client-side)
    await RUN_BUS.emit(run_id, f'{{"type":"log","level":"info","message":"JD scraped ({len(jd_text)} chars)"}}')
    await RUN_BUS.emit(run_id, f'{{"type":"jd","ts":"","text":{repr(jd_text)}}}')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--force-device-scale-factor=1"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 860})
        page1 = await ctx.new_page()
        await page1.goto("https://chat.openai.com/", wait_until="domcontentloaded")
        await RUN_BUS.emit(run_id, '{"type":"log","level":"info","message":"Opened chat.openai.com (please sign in)"}')

        page2 = await ctx.new_page()
        await page2.goto(job_url, wait_until="domcontentloaded")
        await RUN_BUS.emit(run_id, f'{{"type":"log","level":"info","message":"Opened job page: {job_url}"}}')

        # Pause until user finishes in ChatGPT and submits JSON via UI
        await RUN_BUS.emit(run_id, '{"type":"gate","prompt":"In the VNC window: 1) Sign in to ChatGPT 2) Upload your resume (paperclip) 3) Paste the prompt from the UI 4) Copy the JSON result back into the UI and click Render."}')
        # The run ends once the UI posts JSON to /tailor/import-json; nothing else to do here.
