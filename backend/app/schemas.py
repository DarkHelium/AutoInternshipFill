from pydantic import BaseModel
from typing import List, Optional, Dict

class JobOut(BaseModel):
    id: str
    company: str
    role: str
    location: Optional[str] = None
    apply_url: str
    date_posted: Optional[str] = None
    ats: Optional[str] = "other"
    status: str

class ProfileIn(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    school: Optional[str] = None
    grad_date: Optional[str] = None
    work_auth: Optional[Dict] = None
    links: Optional[Dict] = None
    skills: Optional[List[str]] = None
    answers: Optional[Dict] = None

class ProfileOut(ProfileIn):
    id: str
    base_resume_url: Optional[str] = None

class TailorResultOut(BaseModel):
    jobId: str
    keywords: List[str]
    diffHtml: str | None = None
    pdfUrl: str | None = None
