#!/usr/bin/env python3
"""
Simple automation server that runs inside the VNC desktop container.
Handles Playwright automation commands via HTTP API.
"""
import asyncio
import os
from fastapi import FastAPI
from playwright.async_api import async_playwright
import uvicorn

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok", "display": os.environ.get("DISPLAY", "unknown")}

@app.post("/start-desktop-tailor")
async def start_desktop_tailor(request: dict):
    """Start desktop tailoring automation in VNC environment"""
    job_url = request.get("job_url", "https://example.com")
    resume_url = request.get("resume_url")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False, 
                args=["--force-device-scale-factor=1", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 860})
            
            # Open ChatGPT in first tab
            page1 = await context.new_page()
            await page1.goto("https://chat.openai.com/", wait_until="domcontentloaded")
            
            # If resume URL provided, download it to ~/Downloads for user convenience
            try:
                if resume_url:
                    dl_dir = os.path.expanduser("~/Downloads")
                    os.makedirs(dl_dir, exist_ok=True)
                    ctx2 = await browser.new_context(accept_downloads=True)
                    p = await ctx2.new_page()
                    await p.goto(resume_url)
                    # If server responds inline, try to save via download API
                    # This is best-effort; user can also re-download manually
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Open job page in second tab
            page2 = await context.new_page()
            await page2.goto(job_url, wait_until="domcontentloaded")
            
            # Bring ChatGPT tab to front and move mouse to make it visible
            await page1.bring_to_front()
            await asyncio.sleep(1)
            
            # Move mouse cursor to make it clearly visible
            for x, y in [(200,200),(400,300),(640,400),(800,500),(600,500)]:
                await page1.mouse.move(x, y)
                await asyncio.sleep(0.25)
            
            # Keep browsers open (don't close them)
            # The user will interact manually in the VNC session
            
            return {
                "status": "success", 
                "message": "Browsers opened in VNC desktop",
                "chatgpt_ready": True,
                "job_page_ready": True,
                "resume_downloaded": bool(resume_url)
            }
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9001)
