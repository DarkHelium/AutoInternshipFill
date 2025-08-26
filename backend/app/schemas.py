from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class JobOut(BaseModel):
    id: str
    company: str
    role: str
    location: Optional[str] = None
    apply_url: str
    date_posted: Optional[str] = None
    ats: Optional[str] = "other"
    status: str
    # AI Analysis fields
    job_description: Optional[str] = None
    key_requirements: Optional[List[str]] = None
    salary_range: Optional[str] = None
    remote_policy: Optional[str] = None
    difficulty_score: Optional[float] = None
    match_score: Optional[float] = None

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
    # AI Career Co-pilot fields
    career_constraints: Optional[Dict] = None
    ai_api_key: Optional[str] = None
    preferred_ai_model: Optional[str] = "gpt-5"
    experience_level: Optional[str] = None
    target_roles: Optional[List[str]] = None
    salary_expectations: Optional[Dict] = None
    location_preferences: Optional[Dict] = None

class ProfileOut(ProfileIn):
    id: str
    base_resume_url: Optional[str] = None

class TailorResultOut(BaseModel):
    jobId: str
    keywords: List[str]
    diffHtml: str | None = None
    pdfUrl: str | None = None
    # AI Enhancement fields
    ai_analysis: Optional[Dict] = None
    tailoring_strategy: Optional[str] = None
    ats_score: Optional[float] = None
    improvement_suggestions: Optional[List[str]] = None

# New schemas for AI career co-pilot features
class JobAnalysisRequest(BaseModel):
    job_url: str
    job_description: Optional[str] = None  # If user pastes JD directly

class JobAnalysisResponse(BaseModel):
    job_id: str
    key_requirements: List[str]
    difficulty_score: float
    match_score: float
    ai_analysis: Dict[str, Any]
    suggested_improvements: List[str]

class ResumeTailoringRequest(BaseModel):
    job_id: str
    user_constraints: Optional[Dict] = None  # Any specific user preferences

class ResumeTailoringResponse(BaseModel):
    tailored_resume: Dict[str, Any]  # JSON structure of resume
    changes_explanation: str
    ats_score: float
    keyword_integration: List[str]

class ApplicationOutcomeUpdate(BaseModel):
    job_id: str
    status: str  # applied|viewed|phone_screen|interview|offer|rejected|no_response
    outcome_date: Optional[datetime] = None
    notes: Optional[str] = None
    feedback_received: Optional[str] = None

class AIInteractionFeedback(BaseModel):
    interaction_id: str
    user_rating: int  # 1-5 stars
    feedback_notes: Optional[str] = None
