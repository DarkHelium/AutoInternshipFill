import os, json, asyncio
from typing import List, Optional
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
# WeasyPrint is optional at import time; server should still boot without it
try:
    from weasyprint import HTML  # type: ignore
except Exception:  # pragma: no cover - environment without weasyprint
    HTML = None  # type: ignore
# Optional libmagic for MIME detection; fallback to simple PDF signature check
try:
    import magic  # type: ignore
except Exception:  # libmagic may be missing on some systems
    magic = None  # type: ignore

from .db import Base, engine, get_db
from .models import Job, Run, Profile, TailorResult
from .schemas import JobOut, ProfileIn, ProfileOut, TailorResultOut
from .ingest import fetch_readme, parse_jobs_from_readme
from .ats import detect_ats
from .tailor import extract_keywords, make_diff_html
from .runners.run_manager import RUN_BUS, gate_for
from .runners.greenhouse import greenhouse_prefill, greenhouse_prefill_headed
from .runners.desktop_tailor import desktop_tailor_run
from .runners.oneclick import oneclick_tailor_apply

load_dotenv()
app = FastAPI(title="Auto Apply Backend")

origins_env = os.getenv("CORS_ORIGINS")
origins = [o.strip() for o in (origins_env or "").split(",") if o.strip()]
if not origins:
    # Sensible default for local dev
    origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

files_dir = os.getenv("FILES_DIR", "./files")
os.makedirs(files_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=files_dir), name="files")

Base.metadata.create_all(bind=engine)

# Initialize Jinja2 environment for PDF rendering
env = Environment(loader=FileSystemLoader("./templates"))
resume_tpl = env.get_template("resume.html")

def render_pdf_from_json(resume_json: dict, out_path: str):
    html = resume_tpl.render(r=resume_json)
    if HTML is None:
        # Defer failure until actually attempting to render a PDF
        raise HTTPException(500, "WeasyPrint is not installed. Install 'weasyprint==62.3' to enable PDF rendering.")
    HTML(string=html, base_url=".").write_pdf(out_path)

def validate_pdf_file(file_path: str) -> bool:
    """Validate that the file is a PDF.

    Prefer libmagic when available; otherwise fall back to checking the
    standard PDF header signature to avoid hard failure when libmagic
    isn't installed on the host.
    """
    # Prefer libmagic if present and working
    if magic is not None:
        try:
            mime_type = magic.from_file(file_path, mime=True)
            if mime_type == 'application/pdf':
                return True
        except Exception:
            # fall through to header check
            pass

    # Fallback: check file starts with %PDF- and has EOF marker
    try:
        with open(file_path, 'rb') as f:
            head = f.read(5)
        if head != b"%PDF-":
            return False
        # Optionally check for EOF within last 1KB
        with open(file_path, 'rb') as f:
            try:
                f.seek(-1024, os.SEEK_END)
            except OSError:
                f.seek(0)
            tail = f.read()
        return b"%%EOF" in tail
    except Exception:
        return False

@app.get("/health")
def health():
    return {"ok": True}

def _ingest_into_db(db: Session) -> int:
    owner = os.getenv("GITHUB_OWNER", "vanshb03")
    repo = os.getenv("GITHUB_REPO", "Summer2026-Internships")
    branch = os.getenv("GITHUB_BRANCH", "dev")
    token = os.getenv("GITHUB_TOKEN")

    md = fetch_readme(owner, repo, branch, token)
    rows = parse_jobs_from_readme(md)
    count = 0
    for r in rows:
        exists = db.query(Job).filter(
            Job.company==r["company"], Job.role==r["role"], Job.apply_url==r["apply_url"]
        ).first()
        if exists:
            continue
        j = Job(company=r["company"], role=r["role"], location=r["location"],
                apply_url=r["apply_url"], date_posted=r["date_posted"],
                ats=detect_ats(r["apply_url"]), raw_line=r["raw_line"])
        db.add(j); count += 1
    db.commit()
    return count

def _ensure_jobs_seeded(db: Session):
    if db.query(Job).count() == 0:
        _ingest_into_db(db)

@app.post("/admin/ingest")
def ingest(db: Session = Depends(get_db)):
    added = _ingest_into_db(db)
    return {"added": added, "total": db.query(Job).count()}

# ----- Jobs -----
@app.get("/jobs", response_model=List[JobOut])
def list_jobs(db: Session = Depends(get_db)):
    _ensure_jobs_seeded(db)
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

# One-click tailor + apply
@app.post("/jobs/{job_id}/oneclick")
async def oneclick(job_id: str, db: Session = Depends(get_db)):
    j = db.query(Job).get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    run = Run(job_id=job_id)
    db.add(run); db.commit()
    asyncio.create_task(oneclick_tailor_apply(run.id, j.role or "", j.apply_url, j.raw_line or j.role or "", files_dir))
    return {"runId": run.id}

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
    
    # Guard: ensure we have a valid base resume PDF
    profile = db.query(Profile).filter(Profile.id == "default").first()
    if not profile or not profile.base_resume_url:
        raise HTTPException(400, "No base resume uploaded. Please upload a PDF first.")
    
    # Extract filename from URL path and validate the PDF file exists and is valid
    if profile.base_resume_url.startswith("/files/"):
        filename = profile.base_resume_url.replace("/files/", "")
        file_path = os.path.join(files_dir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(400, "Base resume file not found. Please re-upload your PDF.")
        
        if not validate_pdf_file(file_path):
            raise HTTPException(400, "Base resume is not a valid PDF. Please upload a valid PDF file.")
    else:
        raise HTTPException(400, "Invalid resume URL format. Please re-upload your PDF.")
    
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

# Upload endpoints for resume handling
@app.post("/uploads/resumeUrl")
def get_resume_upload_url():
    """Generate a presigned URL for resume upload"""
    import uuid
    filename = f"resume_{uuid.uuid4().hex}.pdf"
    # Important: do NOT upload to the StaticFiles mount. Use a separate API path
    # StaticFiles mounted at /files will swallow PUTs otherwise.
    upload_path = f"/upload/{filename}"
    public_url = f"/files/{filename}"
    
    return {
        "uploadUrl": upload_path,
        "publicUrl": public_url
    }

@app.put("/upload/{filename}")
async def upload_file(filename: str, request: Request):
    """Handle file upload with PDF validation. Writes into files_dir."""
    os.makedirs(files_dir, exist_ok=True)
    file_path = os.path.join(files_dir, filename)
    
    body = await request.body()
    with open(file_path, "wb") as f:
        f.write(body)
    
    # Validate it's actually a PDF
    if not validate_pdf_file(file_path):
        os.remove(file_path)  # Clean up invalid file
        raise HTTPException(400, "File is not a valid PDF")
    
    return {"ok": True}

# Profile endpoints
@app.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    """Get applicant profile"""
    p = db.query(Profile).filter(Profile.id == "default").first()
    if not p:
        p = Profile(id="default", name="", email="")
        db.add(p)
        db.commit()
    
    return {
        "name": p.name or "",
        "email": p.email or "",
        "phone": p.phone or "",
        "school": p.school or "",
        "gradDate": p.grad_date or "",
        "workAuth": p.work_auth or {"usCitizen": False, "sponsorship": False},
        "links": p.links or {"github": "", "portfolio": "", "linkedin": ""},
        "skills": p.skills or [],
        "answers": p.answers or {},
        "base_resume_url": p.base_resume_url or ""
    }

@app.put("/profile")
def update_profile(profile_data: dict = Body(...), db: Session = Depends(get_db)):
    """Update applicant profile (persist all recognized fields)."""
    p = db.query(Profile).filter(Profile.id == "default").first()
    if not p:
        p = Profile(id="default")
        db.add(p)

    # Basic fields
    p.name = profile_data.get("name", p.name or "")
    p.email = profile_data.get("email", p.email or "")
    p.phone = profile_data.get("phone", p.phone or "")
    p.school = profile_data.get("school", p.school or "")
    p.grad_date = profile_data.get("gradDate", p.grad_date or "")

    # Structured fields
    if "workAuth" in profile_data:
        p.work_auth = profile_data.get("workAuth") or {}
    if "links" in profile_data:
        p.links = profile_data.get("links") or {}
    if "skills" in profile_data:
        p.skills = profile_data.get("skills") or []
    if "answers" in profile_data:
        p.answers = profile_data.get("answers") or {}

    db.commit()

    # Return the updated profile in the same shape as GET /profile
    return {
        "name": p.name or "",
        "email": p.email or "",
        "phone": p.phone or "",
        "school": p.school or "",
        "gradDate": p.grad_date or "",
        "workAuth": p.work_auth or {"usCitizen": False, "sponsorship": False},
        "links": p.links or {"github": "", "portfolio": "", "linkedin": ""},
        "skills": p.skills or [],
        "answers": p.answers or {},
        "base_resume_url": p.base_resume_url or "",
    }

@app.put("/profile/base-resume")
def set_base_resume(body: dict = Body(...), db: Session = Depends(get_db)):
    """Set the base resume URL"""
    p = db.query(Profile).filter(Profile.id == "default").first()
    if not p:
        p = Profile(id="default", name="", email="")
        db.add(p)
    
    p.base_resume_url = body.get("url", "")
    db.commit()
    
    return {"ok": True}

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
