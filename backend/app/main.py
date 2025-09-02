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
from .models import Job, Run, Profile, TailorResult, ApplicationOutcome, AIInteraction, ResumeVersion
from .schemas import (
    JobOut, ProfileIn, ProfileOut, TailorResultOut,
    JobAnalysisRequest, JobAnalysisResponse, ResumeTailoringRequest, ResumeTailoringResponse,
    ApplicationOutcomeUpdate, AIInteractionFeedback
)
from .ai_services import get_ai_service
from .ingest import fetch_readme, parse_jobs_from_readme
from .ats import detect_ats
from .tailor import extract_keywords, make_diff_html

load_dotenv()
app = FastAPI(title="AI Career Co-pilot Backend")

origins_env = os.getenv("CORS_ORIGINS")
origins = [o.strip() for o in (origins_env or "").split(",") if o.strip()]
if not origins:
    # Sensible default for local dev (Remix 5173, Next.js 3000)
    origins = ["http://localhost:5173", "http://localhost:3000"]
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
try:
    resume_tpl = env.get_template("resume.html")
except Exception:
    resume_tpl = None  # Loaded lazily when PDF rendering is used

def render_pdf_from_json(resume_json: dict, out_path: str):
    if resume_tpl is None:
        raise HTTPException(500, "Missing resume template. Ensure templates/resume.html exists.")
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

# Mount new, cleaner routers for profiles and runs
from .api.routes_profiles import router as profiles_router
from .api.routes_runs import router as runs_router
from .api.routes_openai_compat import router as openai_router
app.include_router(profiles_router)
app.include_router(runs_router)
app.include_router(openai_router)

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

# Chrome Extension Apply - simplified for extension use
@app.post("/jobs/{job_id}/apply")
async def apply(job_id: str, profileId: str = "default", db: Session = Depends(get_db)):
    """Mark job as applied - will be called by Chrome extension"""
    j = db.query(Job).get(job_id)
    if not j: raise HTTPException(404, "job not found")

    j.status = "applied"
    db.commit()
    
    return {"success": True, "message": "Job marked as applied"}

# One-click AI tailor + apply for Chrome extension
@app.post("/jobs/{job_id}/oneclick")
async def oneclick(job_id: str, db: Session = Depends(get_db)):
    """AI-powered one-click tailor and apply for Chrome extension"""
    j = db.query(Job).get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    
    # Analyze job if not already done
    if not j.job_description or not j.key_requirements:
        # Would trigger AI analysis here
        j.status = "needs_analysis"
    else:
        j.status = "ready_to_apply"
    
    db.commit()
    return {"jobId": j.id, "status": j.status, "message": "Ready for Chrome extension application"}

# Removed - no longer needed for Chrome extension

# Removed desktop tailor - replaced with AI API endpoints

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
@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload resume file directly using multipart/form-data"""
    if not file.filename:
        raise HTTPException(400, "No file selected")
    
    # Validate file type
    allowed_types = {'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "Invalid file type. Please upload PDF, DOC, or DOCX files only")
    
    # Generate unique filename
    import uuid
    ext = os.path.splitext(file.filename)[1]
    filename = f"resume_{uuid.uuid4().hex}{ext}"
    
    # Save file
    os.makedirs(files_dir, exist_ok=True)
    file_path = os.path.join(files_dir, filename)
    
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        return {
            "success": True,
            "filename": filename,
            "publicUrl": f"/files/{filename}",
            "message": "Resume uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {str(e)}")

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

# Removed SSE events - not needed for Chrome extension

# ----- AI Career Co-pilot Endpoints -----

@app.post("/ai/analyze-job")
async def analyze_job_description(request: JobAnalysisRequest, db: Session = Depends(get_db)):
    """AI-powered job description analysis"""
    try:
        # Get or create default user profile so the endpoint never hard-fails
        profile = db.query(Profile).get("default")
        if not profile:
            profile = Profile(id="default", name="", email="")
            db.add(profile)
            db.commit()
        
        # Get user's AI settings
        ai_service = get_ai_service(
            user_api_key=profile.ai_api_key,
            model=profile.preferred_ai_model or os.getenv("DEFAULT_AI_MODEL", "deepseek-reasoner")
        )
        
        # Enhanced job scraping with Playwright if URL provided
        job_description = request.job_description
        job_details = {}
        if not job_description and request.job_url:
            try:
                from .playwright_service import enhanced_job_scraping
                job_details = await enhanced_job_scraping(request.job_url)
                job_description = job_details.get('description', '')
            except Exception as e:
                # Fallback to basic scraping
                try:
                    import httpx
                    from bs4 import BeautifulSoup
                    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                        response = await client.get(request.job_url)
                    soup = BeautifulSoup(response.text, "lxml")
                    content = soup.select_one("main, .content, #content, .job, article") or soup
                    job_description = content.get_text(" ", strip=True)
                    job_details = {'company': 'Unknown', 'title': 'Unknown'}
                except Exception as fallback_error:
                    raise HTTPException(400, f"Failed to scrape job description: {str(fallback_error)}")
        
        if not job_description:
            raise HTTPException(400, "No job description provided")
        
        # Prepare user profile for AI analysis
        user_profile = {
            "experience_level": profile.experience_level,
            "skills": profile.skills or [],
            "target_roles": profile.target_roles or [],
            "work_auth": profile.work_auth or {},
            "education": profile.school,
            "grad_date": profile.grad_date
        }
        
        # Run AI analysis
        analysis = await ai_service.analyze_job_description(
            request.job_url, job_description, user_profile
        )
        
        # Find or create job record
        job = db.query(Job).filter(Job.apply_url == request.job_url).first()
        if not job:
            # Create new job record with enhanced scraped data and AI analysis
            job = Job(
                company=job_details.get("company", "Unknown"),
                role=job_details.get("title", "Unknown"),
                location=job_details.get("location"),
                apply_url=request.job_url,
                status="analyzing",
                ats=job_details.get("ats", "unknown"),
                job_description=job_description,
                key_requirements=analysis.get("key_requirements", []),
                salary_range=analysis.get("salary_range"),
                remote_policy=analysis.get("remote_policy"),
                difficulty_score=analysis.get("difficulty_score"),
                match_score=analysis.get("match_score")
            )
            db.add(job)
            db.commit()
        else:
            # Update existing job with enhanced data and AI analysis
            job.company = job_details.get("company", job.company)
            job.role = job_details.get("title", job.role)
            job.location = job_details.get("location", job.location)
            job.ats = job_details.get("ats", job.ats)
            job.job_description = job_description
            job.key_requirements = analysis.get("key_requirements", [])
            job.salary_range = analysis.get("salary_range")
            job.remote_policy = analysis.get("remote_policy")
            job.difficulty_score = analysis.get("difficulty_score")
            job.match_score = analysis.get("match_score")
            job.status = "analyzed"
            db.commit()
        
        return JobAnalysisResponse(
            job_id=job.id,
            key_requirements=analysis.get("key_requirements", []),
            difficulty_score=analysis.get("difficulty_score", 0.5),
            match_score=analysis.get("match_score", 0.5),
            ai_analysis=analysis,
            suggested_improvements=analysis.get("improvement_suggestions", [])
        )
        
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {str(e)}")

@app.post("/ai/tailor-resume")
async def tailor_resume(request: ResumeTailoringRequest, db: Session = Depends(get_db)):
    """AI-powered resume tailoring"""
    try:
        # Get job and user profile
        job = db.query(Job).get(request.job_id)
        if not job:
            raise HTTPException(404, "Job not found")
            
        profile = db.query(Profile).get("default")
        if not profile or not profile.base_resume_url:
            raise HTTPException(400, "Please upload a base resume first")
        
        # Get AI service
        ai_service = get_ai_service(
            user_api_key=profile.ai_api_key,
            model=profile.preferred_ai_model or os.getenv("DEFAULT_AI_MODEL", "deepseek-reasoner")
        )
        
        # Prepare job analysis for AI
        job_analysis = {
            "key_requirements": job.key_requirements or [],
            "difficulty_score": job.difficulty_score or 0.5,
            "match_score": job.match_score or 0.5,
            "job_description": job.job_description or "",
            "company": job.company,
            "role": job.role
        }
        
        # Get base resume content (simplified for now - would need PDF parsing)
        base_resume = f"""
        Name: {profile.name}
        Email: {profile.email}
        Phone: {profile.phone}
        School: {profile.school}
        Graduation: {profile.grad_date}
        Skills: {', '.join(profile.skills or [])}
        """
        
        # Combine user constraints
        user_constraints = profile.career_constraints or {}
        if request.user_constraints:
            user_constraints.update(request.user_constraints)
        
        # Run AI tailoring
        tailoring_result = await ai_service.tailor_resume(
            job_analysis, base_resume, user_constraints
        )
        
        # Store tailoring result
        tailor_result = TailorResult(
            job_id=request.job_id,
            keywords=tailoring_result.get("keyword_integration", []),
            ai_analysis=tailoring_result,
            tailoring_strategy=tailoring_result.get("changes_explanation", ""),
            ats_score=tailoring_result.get("ats_score", 0.0),
            improvement_suggestions=tailoring_result.get("improvement_suggestions", [])
        )
        db.add(tailor_result)
        
        # Update job status
        job.status = "tailored"
        db.commit()
        
        return ResumeTailoringResponse(
            tailored_resume=tailoring_result.get("tailored_resume", {}),
            changes_explanation=tailoring_result.get("changes_explanation", ""),
            ats_score=tailoring_result.get("ats_score", 0.0),
            keyword_integration=tailoring_result.get("keyword_integration", [])
        )
        
    except HTTPException as he:
        # Propagate explicit HTTP errors (e.g., 400 when resume missing)
        raise he
    except Exception as e:
        raise HTTPException(500, f"Resume tailoring failed: {str(e)}")

@app.post("/ai/ats-preview")
async def generate_ats_preview(job_id: str, db: Session = Depends(get_db)):
    """Generate ATS preview of tailored resume"""
        # Get latest tailoring result for job
    tailor_result = db.query(TailorResult).filter(
            TailorResult.job_id == job_id
    ).order_by(TailorResult.created_at.desc()).first()
        
    if not tailor_result or not tailor_result.ai_analysis:
        raise HTTPException(404, "No tailored resume found for this job")
        
    profile = db.query(Profile).get("default")
    ai_service = get_ai_service(
            user_api_key=profile.ai_api_key if profile else None,
            model=(profile.preferred_ai_model if profile and profile.preferred_ai_model else os.getenv("DEFAULT_AI_MODEL", "deepseek-reasoner"))
    )

    # Get tailored resume content and produce ATS preview
    tailored_resume = tailor_result.ai_analysis.get("tailored_resume", {})
    ats_preview = await ai_service.generate_ats_preview(tailored_resume)
    return ats_preview

@app.post("/profile/bootstrap-jake-resume")
def bootstrap_jake_resume(db: Session = Depends(get_db)):
    """Create a simple 'Jake' resume PDF from template and set as base resume.
    This helps during first-run when the user hasn't uploaded a resume yet.
    """
    # Minimal resume JSON for template
    resume_json = {
        "name": "Jake Applicant",
        "contact": {"email": "jake@example.com", "phone": "(555) 123-4567", "location": "San Francisco, CA"},
        "summary": "Computer Science student with internships in web dev and ML; seeking 2026 SWE internship.",
        "skills": ["Python", "JavaScript", "React", "FastAPI", "SQL"],
        "experience": [
            {"company": "Campus Lab", "title": "Software Intern", "start_date": "2025-06", "end_date": "2025-08",
             "bullets": ["Built internal dashboards with React/Flask", "Improved API latency by 25%"]}
        ],
        "projects": [
            {"name": "Course Planner", "description": "Full‑stack planner for students", "bullets": ["React + FastAPI", "Deployed on Render"]}
        ],
        "education": [{"school": "State University", "degree": "B.S. Computer Science", "graduation": "2026"}]
    }
    os.makedirs(files_dir, exist_ok=True)
    out_path = os.path.join(files_dir, "resume_jake.pdf")
    render_pdf_from_json(resume_json, out_path)
    # Set base resume URL
    p = db.query(Profile).get("default") or Profile(id="default", name="", email="")
    db.add(p)
    p.base_resume_url = f"/files/{os.path.basename(out_path)}"
    db.commit()
    return {"ok": True, "url": p.base_resume_url}

@app.get("/ai/ats-preview")
async def generate_ats_preview_get(job_id: str, db: Session = Depends(get_db)):
    """GET variant for ATS preview so extensions can open it in a new tab."""
    return await generate_ats_preview(job_id, db)

@app.post("/ai/track-outcome")
async def track_application_outcome(outcome: ApplicationOutcomeUpdate, db: Session = Depends(get_db)):
    """Track application outcome for learning"""
    try:
        # Find or create outcome record
        existing = db.query(ApplicationOutcome).filter(
            ApplicationOutcome.job_id == outcome.job_id
        ).first()
        
        if existing:
            existing.status = outcome.status
            existing.outcome_date = outcome.outcome_date
            existing.notes = outcome.notes
            existing.feedback_received = outcome.feedback_received
        else:
            outcome_record = ApplicationOutcome(
                job_id=outcome.job_id,
                status=outcome.status,
                outcome_date=outcome.outcome_date,
                notes=outcome.notes,
                feedback_received=outcome.feedback_received
            )
            db.add(outcome_record)
        
        # Update job status
        job = db.query(Job).get(outcome.job_id)
        if job:
            job.status = outcome.status
        
        db.commit()
        return {"success": True, "message": "Outcome tracked successfully"}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to track outcome: {str(e)}")

@app.post("/ai/feedback")
async def submit_ai_feedback(feedback: AIInteractionFeedback, db: Session = Depends(get_db)):
    """Submit feedback on AI interaction quality"""
    try:
        interaction = db.query(AIInteraction).get(feedback.interaction_id)
        if not interaction:
            raise HTTPException(404, "AI interaction not found")
        
        interaction.user_rating = feedback.user_rating
        db.commit()
        
        return {"success": True, "message": "Feedback recorded"}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to record feedback: {str(e)}")

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

# Note: unified base-resume setter above; keep only JSON body variant to avoid conflicts
