import os, json, asyncio
from typing import List, Optional
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from .db import Base, engine, get_db
from .models import Job, Run, Profile, TailorResult
from .schemas import JobOut, ProfileIn, ProfileOut, TailorResultOut
from .ingest import fetch_readme, parse_jobs_from_readme
from .ats import detect_ats
from .tailor import extract_keywords, make_diff_html
from .runners.run_manager import RUN_BUS, gate_for
from .runners.greenhouse import greenhouse_prefill, greenhouse_prefill_headed
from .runners.desktop_tailor import desktop_tailor_run

load_dotenv()
app = FastAPI(title="Auto Apply Backend")

origins = [o.strip() for o in (os.getenv("CORS_ORIGINS") or "").split(",") if o.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

files_dir = os.getenv("FILES_DIR", "./files")
os.makedirs(files_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=files_dir), name="files")

Base.metadata.create_all(bind=engine)

# Initialize Jinja2 environment for PDF rendering
env = Environment(loader=FileSystemLoader("./templates"))
resume_tpl = env.get_template("resume.html")

def render_pdf_from_json(resume_json: dict, out_path: str):
    html = resume_tpl.render(r=resume_json)
    HTML(string=html, base_url=".").write_pdf(out_path)

@app.get("/health")
def health():
    return {"ok": True}

# ----- Ingest -----
@app.post("/admin/ingest")
def ingest(db: Session = Depends(get_db)):
    owner = os.getenv("GITHUB_OWNER", "vanshb03")
    repo = os.getenv("GITHUB_REPO", "Summer2026-Internships")
    branch = os.getenv("GITHUB_BRANCH", "dev")
    token = os.getenv("GITHUB_TOKEN")

    md = fetch_readme(owner, repo, branch, token)
    rows = parse_jobs_from_readme(md)
    count = 0
    for r in rows:
        exists = db.query(Job).filter(Job.company==r["company"], Job.role==r["role"], Job.apply_url==r["apply_url"]).first()
        if exists: continue
        j = Job(company=r["company"], role=r["role"], location=r["location"],
                apply_url=r["apply_url"], date_posted=r["date_posted"],
                ats=detect_ats(r["apply_url"]), raw_line=r["raw_line"])
        db.add(j); count += 1
    db.commit()
    return {"added": count, "total": db.query(Job).count()}

# ----- Jobs -----
@app.get("/jobs", response_model=List[JobOut])
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).order_by(Job.date_posted.desc().nullslast()).all()
    return [JobOut(id=j.id, company=j.company, role=j.role, location=j.location,
                   apply_url=j.apply_url, date_posted=j.date_posted, ats=j.ats, status=j.status)
            for j in jobs]

@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    j = db.query(Job).get(job_id)
    if not j: raise HTTPException(404, "job not found")
    return JobOut(id=j.id, company=j.company, role=j.role, location=j.location,
                  apply_url=j.apply_url, date_posted=j.date_posted, ats=j.ats, status=j.status)

# Latest tailor result
@app.get("/jobs/{job_id}/tailor/latest", response_model=Optional[TailorResultOut])
def latest_tailor(job_id: str, db: Session = Depends(get_db)):
    tr = db.query(TailorResult).filter(TailorResult.job_id==job_id).order_by(TailorResult.created_at.desc()).first()
    if not tr: return None
    return TailorResultOut(jobId=tr.job_id, keywords=tr.keywords, diffHtml=tr.diff_html, pdfUrl=tr.pdf_url)

# Tailor (MVP keywords + diff preview)
@app.post("/jobs/{job_id}/tailor", response_model=TailorResultOut)
def tailor(job_id: str, profileId: str = "default", db: Session = Depends(get_db)):
    j = db.query(Job).get(job_id)
    if not j: raise HTTPException(404, "job not found")

    # Fetch JD text (MVP: just GET and strip tags)
    import httpx
    from bs4 import BeautifulSoup
    jd_text = ""
    try:
        r = httpx.get(j.apply_url, timeout=20, follow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        # try common content containers, else all text
        cont = soup.select_one("div#content, .content, .job, main") or soup
        jd_text = cont.get_text(separator=" ", strip=True)
    except Exception:
        pass

    kws = extract_keywords(jd_text, top_k=10)
    prof = db.query(Profile).get(profileId)
    base_resume_text = ""  # If you want, fetch & parse PDF here
    diff_html = make_diff_html(base_resume_text, kws)
    tr = TailorResult(job_id=job_id, keywords=kws, diff_html=diff_html, pdf_url=None)
    db.add(tr); db.commit()
    j.status = "tailored"; db.commit()

    return TailorResultOut(jobId=job_id, keywords=kws, diffHtml=diff_html, pdfUrl=None)

# Apply (launches a run + SSE logs)
@app.post("/jobs/{job_id}/apply")
async def apply(job_id: str, profileId: str = "default", db: Session = Depends(get_db)):
    j = db.query(Job).get(job_id)
    if not j: raise HTTPException(404, "job not found")

    # Set VNC URL from environment
    vnc_url = os.getenv("DESKTOP_NOVNC", "http://localhost:6080/vnc.html?autoconnect=true")
    
    run = Run(job_id=job_id, vnc_url=vnc_url, display=":20")
    db.add(run); db.commit()
    run_id = run.id

    # Emit VNC URL immediately so UI can show iframe
    await RUN_BUS.emit(run_id, json.dumps({"type":"vnc","url":vnc_url}))

    # Background task: pick ATS
    async def runner():
        try:
            await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"info","message":f"ATS={j.ats}"}))
            if j.ats == "greenhouse":
                await greenhouse_prefill_headed(run_id, j.apply_url, files_dir)
            else:
                await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"warn","message":"ATS not implemented; opening page"}))
                await greenhouse_prefill_headed(run_id, j.apply_url, files_dir)  # still open + screenshot
            run.ok = True
        except Exception as e:
            await RUN_BUS.emit(run_id, json.dumps({"type":"log","level":"error","message":str(e)}))
            await RUN_BUS.emit(run_id, json.dumps({"type":"done","ok":False}))
            run.ok = False
        finally:
            db.add(run); db.commit()

    asyncio.create_task(runner())
    return {"runId": run_id}

# Continue endpoint for approval gate
@app.post("/runs/{run_id}/continue")
async def continue_run(run_id: str):
    ev = gate_for(run_id)
    ev.set()
    return {"ok": True}

# Desktop tailor endpoints
@app.post("/jobs/{job_id}/tailor/desktop/start")
async def start_desktop_tailor(job_id: str, db: Session = Depends(get_db)):
    j = db.query(Job).get(job_id)
    if not j: raise HTTPException(404, "job not found")
    run = Run(job_id=job_id); db.add(run); db.commit()

    # Emit noVNC URL early so Remix can show the desktop immediately
    vnc_url = os.getenv("DESKTOP_NOVNC", "http://localhost:6080/vnc.html?autoconnect=true")
    await RUN_BUS.emit(run.id, json.dumps({"type":"vnc","url":vnc_url}))

    asyncio.create_task(desktop_tailor_run(run.id, j.apply_url))
    return {"runId": run.id, "vncUrl": vnc_url}

@app.post("/jobs/{job_id}/tailor/import-json")
def import_tailored_json(job_id: str,
                         body: dict = Body(...),  # expects {"keywords":[...], "resume":{...}}
                         db: Session = Depends(get_db)):
    j = db.query(Job).get(job_id)
    if not j: raise HTTPException(404, "job not found")

    # validate minimal structure
    if "resume" not in body or "keywords" not in body:
        raise HTTPException(400, "Expected keys: keywords[], resume{}")

    # render PDF
    os.makedirs(files_dir, exist_ok=True)
    out_path = os.path.join(files_dir, f"resume_tailored_{job_id}.pdf")
    render_pdf_from_json(body["resume"], out_path)

    tr = TailorResult(job_id=job_id, keywords=body["keywords"], diff_html=None,
                      pdf_url=f"/files/{os.path.basename(out_path)}")
    db.add(tr); j.status="tailored"; db.commit()
    return {"pdfUrl": tr.pdf_url, "keywords": tr.keywords}

# SSE events
@app.get("/runs/{run_id}/events")
async def run_events(run_id: str):
    async def event_gen():
        # send a hello event so UI shows immediately
        yield b"data: {\"type\":\"log\",\"level\":\"info\",\"message\":\"connected\"}\n\n"
        async for chunk in RUN_BUS.stream(run_id):
            yield chunk
    return StreamingResponse(event_gen(), media_type="text/event-stream")

# ----- Profile -----
@app.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    p = db.query(Profile).get("default")
    if not p:
        p = Profile(id="default", name="", email="")
        db.add(p); db.commit()
    return ProfileOut(id=p.id, name=p.name or "", email=p.email or "", phone=p.phone,
                      school=p.school, grad_date=p.grad_date, work_auth=p.work_auth,
                      links=p.links, skills=p.skills, answers=p.answers, base_resume_url=p.base_resume_url)

@app.put("/profile", response_model=ProfileOut)
def put_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = db.query(Profile).get("default")
    if not p: p = Profile(id="default")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.add(p); db.commit()
    return get_profile(db)

# ----- Uploads (simple direct POST) -----
@app.post("/uploads/resumeUrl")
def create_presigned_like():
    # For simplicity: we won't presign; front-end will still PUT here
    import uuid
    token = str(uuid.uuid4())
    target = f"/uploads/put/{token}"
    public = f"/files/{token}.pdf"
    # stash mapping in memory (demo)
    app.state._upload_map = getattr(app.state, "_upload_map", {})
    app.state._upload_map[token] = os.path.join(files_dir, f"{token}.pdf")
    return {"uploadUrl": target, "publicUrl": public}

@app.put("/uploads/put/{token}")
async def receive_put(token: str, body: bytes = File(default=None)):
    path = getattr(app.state, "_upload_map", {}).get(token)
    if not path:
        raise HTTPException(404, "token not found")
    with open(path, "wb") as f:
        f.write(body if body is not None else b"")
    return {"ok": True}

@app.put("/profile/base-resume")
def set_base_resume(url: str, db: Session = Depends(get_db)):
    p = db.query(Profile).get("default")
    if not p: p = Profile(id="default")
    p.base_resume_url = url
    db.add(p); db.commit()
    return {"ok": True, "url": url}
