import os, asyncio, httpx
from bs4 import BeautifulSoup
from ..runners.run_manager import RUN_BUS
from ..db import SessionLocal
from ..models import Profile

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
    """Trigger browser automation in VNC desktop environment via API"""
    
    await RUN_BUS.emit(run_id, '{"type":"log","level":"info","message":"Launching desktop for tailoring..."}')
    jd_text = await scrape_jd(job_url)
    # send JD text to UI (they'll get a "Copy JD" button client-side)
    await RUN_BUS.emit(run_id, f'{{"type":"log","level":"info","message":"JD scraped ({len(jd_text)} chars)"}}')
    await RUN_BUS.emit(run_id, f'{{"type":"jd","ts":"","text":{repr(jd_text)}}}')

    # Call the automation API running inside the VNC desktop container
    desktop_api = os.getenv("DESKTOP_API", "http://localhost:9001")
    # Build a backend-internal URL for the resume so the desktop container can download it
    backend_internal = os.getenv("BACKEND_INTERNAL", "http://backend:8000")
    resume_url = None
    try:
        db = SessionLocal()
        p = db.query(Profile).get("default")
        if p and p.base_resume_url:
            # p.base_resume_url is like "/files/<name>.pdf"; make it absolute for the desktop container
            resume_url = f"{backend_internal}{p.base_resume_url}"
    finally:
        try:
            db.close()
        except Exception:
            pass
    
    try:
        await RUN_BUS.emit(run_id, '{"type":"log","level":"info","message":"Connecting to VNC desktop automation..."}')
        
        async with httpx.AsyncClient() as client:
            payload = {"job_url": job_url}
            if resume_url:
                payload["resume_url"] = resume_url
            response = await client.post(
                f"{desktop_api}/start-desktop-tailor",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                message = result.get('message', 'success')
                await RUN_BUS.emit(run_id, f'{{"type":"log","level":"info","message":"VNC automation started: {message}"}}')
                await RUN_BUS.emit(run_id, '{"type":"log","level":"info","message":"🖱️ Mouse cursor should now be visible in VNC desktop"}')
                await RUN_BUS.emit(run_id, '{"type":"log","level":"info","message":"✅ ChatGPT and job page opened in VNC browser tabs"}')
            else:
                await RUN_BUS.emit(run_id, f'{{"type":"log","level":"error","message":"VNC automation failed: HTTP {response.status_code}"}}')
                
    except Exception as e:
        error_msg = str(e)
        await RUN_BUS.emit(run_id, f'{{"type":"log","level":"error","message":"VNC automation error: {error_msg}"}}')
    
    # Wait for user interaction
    await RUN_BUS.emit(run_id, '{"type":"gate","prompt":"In the VNC window: 1) Sign in to ChatGPT 2) Upload your resume (paperclip) 3) Paste the prompt from the UI 4) Copy the JSON result back into the UI and click Render."}')
    
    # The run ends once the UI posts JSON to /tailor/import-json