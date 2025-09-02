from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from ..db import get_db
from ..models import Job, Run, Profile
from ..schemas import RunCreate, RunOut, RunPayload, ProfileIn

router = APIRouter(prefix="/runs", tags=["runs"])

def _ensure_job(db: Session, job_url: str) -> Job:
    job = db.query(Job).filter(Job.apply_url == job_url).first()
    if not job:
        job = Job(company="", role="", location=None, apply_url=job_url, status="new")
        db.add(job)
        db.commit()
    return job

def _ensure_profile(db: Session, profile_id: Optional[str], profile_in: Optional[ProfileIn]) -> Profile:
    if profile_id:
        prof = db.query(Profile).get(profile_id)
        if not prof:
            raise HTTPException(404, "profile not found")
        return prof
    # default profile
    prof = db.query(Profile).get("default") or Profile(id="default")
    if profile_in:
        for k, v in profile_in.model_dump().items():
            setattr(prof, k, v)
        db.add(prof)
        db.commit()
    else:
        # ensure exists
        db.add(prof)
        db.commit()
    return prof

@router.post("", response_model=RunOut)
def create_run(body: RunCreate, db: Session = Depends(get_db)):
    job = _ensure_job(db, body.job_url)
    profile = _ensure_profile(db, body.profile_id, body.profile)
    # Optional: try to enrich job with Playwright scrape
    try:
        from ..playwright_service import enhanced_job_scraping
        import asyncio
        details = asyncio.get_event_loop().run_until_complete(enhanced_job_scraping(body.job_url))
        if details:
            job.company = details.get("company") or job.company
            job.role = details.get("title") or job.role
            job.location = details.get("location") or job.location
            job.job_description = details.get("description") or job.job_description
            db.commit()
    except Exception:
        pass
    run = Run(job_id=job.id)
    db.add(run)
    db.commit()
    return RunOut(id=run.id, job_id=job.id, job_url=body.job_url, profile_id=profile.id, status="created")

@router.get("/{run_id}/payload", response_model=RunPayload)
def get_run_payload(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).get(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    job = db.query(Job).get(run.job_id)
    profile = db.query(Profile).get("default")
    if not profile:
        raise HTTPException(400, "no profile available")

    # Build a minimal resume-like structure the extension can consume
    tailored_resume = {
        "name": profile.name or "",
        "contact": {
            "email": profile.email or "",
            "phone": profile.phone or "",
            "location": profile.location_preferences.get("preferred_location") if isinstance(profile.location_preferences, dict) else (profile.school or ""),
            "linkedin": (profile.links or {}).get("linkedin", ""),
            "github": (profile.links or {}).get("github", "")
        },
        "summary": f"Candidate for {job.role or 'role'} with skills: {', '.join(profile.skills or [])}",
        "skills": profile.skills or [],
        "education": ([{"school": profile.school, "degree": "", "graduation": profile.grad_date}] if profile.school else []),
        "experience": []
    }
    return RunPayload(tailored_resume=tailored_resume)
