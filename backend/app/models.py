from sqlalchemy import Column, String, DateTime, Boolean, Text
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
    status = Column(String, default="new")  # new|queued|tailored|applied|skipped|error
    raw_line = Column(Text)

class TailorResult(Base):
    __tablename__ = "tailor_results"
    id = Column(String, primary_key=True, default=uid)
    job_id = Column(String, index=True)
    keywords = Column(SQLiteJSON)
    diff_html = Column(Text)
    pdf_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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

class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True, default=uid)
    job_id = Column(String, index=True)
    ok = Column(Boolean, default=None)
    receipt_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
