from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Profile
from ..schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/default", response_model=ProfileOut)
def get_default_profile(db: Session = Depends(get_db)):
    p = db.get(Profile, "default")
    if not p:
        p = Profile(id="default", name="", email="")
        db.add(p); db.commit()
    return ProfileOut(
        id=p.id,
        name=p.name or "",
        email=p.email or "",
        phone=p.phone,
        school=p.school,
        grad_date=p.grad_date,
        work_auth=p.work_auth,
        links=p.links,
        skills=p.skills,
        answers=p.answers,
        base_resume_url=p.base_resume_url,
        career_constraints=p.career_constraints,
        ai_api_key=p.ai_api_key,
        preferred_ai_model=p.preferred_ai_model,
        experience_level=p.experience_level,
        target_roles=p.target_roles,
        salary_expectations=p.salary_expectations,
        location_preferences=p.location_preferences,
    )

@router.put("/default", response_model=ProfileOut)
def upsert_default_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = db.get(Profile, "default")
    if not p:
        p = Profile(id="default")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.add(p); db.commit()
    return get_default_profile(db)
