from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Float
from sqlalchemy.sql import func
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from .db import Base
import uuid

def uid() -> str:
    return str(uuid.uuid4())

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=uid)
    company = Column(String, index=True)
    role = Column(String, index=True)
    location = Column(String)
    apply_url = Column(String)
    date_posted = Column(String)
    ats = Column(String, default="other")
    status = Column(String, default="new")  # new|analyzing|tailored|applied|interview|rejected|no_response
    raw_line = Column(Text)
    # AI Analysis fields
    job_description = Column(Text, nullable=True)  # Full scraped JD
    key_requirements = Column(SQLiteJSON, nullable=True)  # AI-extracted requirements
    salary_range = Column(String, nullable=True)
    remote_policy = Column(String, nullable=True)  # remote|hybrid|onsite
    difficulty_score = Column(Float, nullable=True)  # AI assessment 0-1
    match_score = Column(Float, nullable=True)  # How well user matches (0-1)

class TailorResult(Base):
    __tablename__ = "tailor_results"
    id = Column(String, primary_key=True, default=uid)
    job_id = Column(String, index=True)
    keywords = Column(SQLiteJSON)
    diff_html = Column(Text)
    pdf_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # AI Enhancement fields
    ai_analysis = Column(SQLiteJSON, nullable=True)  # Full AI analysis of job match
    tailoring_strategy = Column(Text, nullable=True)  # AI explanation of changes
    ats_score = Column(Float, nullable=True)  # Predicted ATS compatibility (0-1)
    improvement_suggestions = Column(SQLiteJSON, nullable=True)  # AI suggestions for better match

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(String, primary_key=True, default="default")
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    school = Column(String)
    grad_date = Column(String)
    work_auth = Column(SQLiteJSON)  # {usCitizen: bool, sponsorship: bool}
    links = Column(SQLiteJSON)      # {github, portfolio, linkedin}
    skills = Column(SQLiteJSON)     # list[str]
    answers = Column(SQLiteJSON)    # map
    base_resume_url = Column(String, nullable=True)
    # AI Career Co-pilot fields
    career_constraints = Column(SQLiteJSON, nullable=True)  # User's preferences and limits
    ai_api_key = Column(String, nullable=True)  # User's own ChatGPT/Claude API key
    preferred_ai_model = Column(String, default="gpt-5")  # gpt-5|claude-4|etc
    experience_level = Column(String, nullable=True)  # entry|mid|senior
    target_roles = Column(SQLiteJSON, nullable=True)  # Preferred job titles/types
    salary_expectations = Column(SQLiteJSON, nullable=True)  # {min, max, currency}
    location_preferences = Column(SQLiteJSON, nullable=True)  # Remote/location prefs

class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True, default=uid)
    job_id = Column(String, index=True)
    ok = Column(Boolean, default=None)
    receipt_url = Column(String, nullable=True)
    desktop_url = Column(String, nullable=True)  # Updated from vnc_url
    display = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# New model for tracking application outcomes and learning
class ApplicationOutcome(Base):
    __tablename__ = "application_outcomes"
    id = Column(String, primary_key=True, default=uid)
    job_id = Column(String, index=True)
    run_id = Column(String, index=True, nullable=True)
    status = Column(String)  # applied|viewed|phone_screen|interview|offer|rejected|no_response
    outcome_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)  # User notes about the application/interview
    feedback_received = Column(Text, nullable=True)  # Any feedback from recruiter
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# New model for AI interactions and learning
class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    id = Column(String, primary_key=True, default=uid)
    job_id = Column(String, index=True, nullable=True)
    interaction_type = Column(String)  # job_analysis|resume_tailoring|ats_preview|suggestion
    prompt = Column(Text)
    response = Column(Text)
    model_used = Column(String)  
    tokens_used = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)  # Track API costs
    user_rating = Column(Integer, nullable=True)  # 1-5 rating of AI response quality
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# New model for resume versions and performance tracking
class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    id = Column(String, primary_key=True, default=uid)
    profile_id = Column(String, default="default")
    job_id = Column(String, index=True, nullable=True)  # If tailored for specific job
    version_name = Column(String)  # "base", "tailored_for_google_swe", etc
    content = Column(Text)  # Raw resume content/JSON
    pdf_url = Column(String, nullable=True)
    is_base_version = Column(Boolean, default=False)
    performance_score = Column(Float, nullable=True)  # Success rate with this version
    created_at = Column(DateTime(timezone=True), server_default=func.now())
