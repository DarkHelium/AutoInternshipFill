"""
AI Services Module for Career Co-pilot
Handles all AI interactions: job analysis, resume tailoring, ATS optimization
"""
import os
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any
import httpx
from .models import Job, Profile, AIInteraction, TailorResult, ResumeVersion
from .db import SessionLocal
import logging

logger = logging.getLogger(__name__)

class AIService:
    """Core AI service for career co-pilot functionality"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-5"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        # Allow overriding base URL to point at a local OpenAI-compatible server
        # Example for host machine service from inside Docker: http://host.docker.internal:11434/v1
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://host.docker.internal:11434/v1")
        
    async def analyze_job_description(self, job_url: str, job_description: str, user_profile: Dict) -> Dict[str, Any]:
        """
        AI analysis of job description to extract requirements and assess fit
        """
        prompt = f"""
        You are an expert career advisor and ATS specialist. Analyze this job description and provide a comprehensive assessment.

        Job Description:
        {job_description}

        User Profile Summary:
        - Experience Level: {user_profile.get('experience_level', 'Not specified')}
        - Skills: {', '.join(user_profile.get('skills', []))}
        - Target Roles: {', '.join(user_profile.get('target_roles', []))}

        Please provide a JSON response with the following structure:
        {{
            "key_requirements": [
                "List of 5-10 most important requirements/skills from the job posting"
            ],
            "salary_range": "Extract salary if mentioned, or null",
            "remote_policy": "remote/hybrid/onsite or null if not specified",
            "difficulty_score": 0.7,  // 0-1 scale based on seniority/requirements
            "match_score": 0.8,  // 0-1 how well user profile matches
            "missing_skills": [
                "Skills user lacks that are required"
            ],
            "competitive_advantages": [
                "User's strengths that align well with this role"
            ],
            "improvement_suggestions": [
                "Specific actionable advice to become a stronger candidate"
            ],
            "ats_keywords": [
                "Critical keywords for ATS optimization"
            ],
            "company_insights": "Brief analysis of company culture/values if discernible"
        }}

        Be honest about match assessment. Consider both hard skills and soft skills.
        """
        
        try:
            response = await self._call_ai_api(prompt, "job_analysis")
            analysis = json.loads(response)
            
            # Store AI interaction for learning
            await self._store_ai_interaction("job_analysis", prompt, response, None)
            
            return analysis
        except Exception as e:
            logger.error(f"Job analysis failed: {e}")
            return self._fallback_job_analysis()

    async def tailor_resume(self, job_analysis: Dict, user_resume: str, user_constraints: Dict = None) -> Dict[str, Any]:
        """
        AI-powered resume tailoring based on job analysis
        """
        constraints_text = ""
        if user_constraints:
            constraints_text = f"""
            USER CONSTRAINTS (MUST FOLLOW):
            {json.dumps(user_constraints, indent=2)}
            """

        prompt = f"""
        You are an expert resume writer and ATS optimization specialist. Tailor this resume for the job requirements while maintaining complete honesty.

        Job Analysis:
        {json.dumps(job_analysis, indent=2)}

        Current Resume Content:
        {user_resume}

        {constraints_text}

        CRITICAL RULES:
        1. NEVER fabricate experience, skills, or qualifications
        2. Only enhance/reframe existing experience to highlight relevance
        3. Use job posting keywords naturally, avoid keyword stuffing
        4. Maintain ATS-friendly formatting (standard section headers)
        5. Keep resume truthful but compelling

        Provide a JSON response with:
        {{
            "tailored_resume": {{
                "name": "User's name",
                "contact": {{
                    "email": "email",
                    "phone": "phone",
                    "location": "location",
                    "linkedin": "linkedin_url",
                    "github": "github_url"
                }},
                "summary": "Professional summary optimized for this role",
                "skills": ["List of relevant skills with job keywords integrated"],
                "experience": [
                    {{
                        "company": "Company name",
                        "title": "Job title",
                        "start_date": "YYYY-MM",
                        "end_date": "YYYY-MM or Present",
                        "bullets": [
                            "Achievement bullets rewritten to highlight job-relevant skills",
                            "Include metrics when possible",
                            "Use action verbs and job keywords naturally"
                        ]
                    }}
                ],
                "projects": [
                    {{
                        "name": "Project name",
                        "description": "Brief description",
                        "bullets": ["Highlight relevant technical skills and outcomes"]
                    }}
                ],
                "education": [
                    {{
                        "school": "University name",
                        "degree": "Degree type",
                        "graduation": "YYYY",
                        "relevant_coursework": "If applicable to job"
                    }}
                ]
            }},
            "changes_explanation": "Clear explanation of what was changed and why",
            "ats_score": 0.85,  // Predicted ATS compatibility 0-1
            "keyword_integration": [
                "List of job keywords successfully integrated"
            ],
            "improvement_suggestions": [
                "Additional suggestions for strengthening the application"
            ]
        }}

        Focus on making the resume compelling for both ATS and human reviewers.
        """
        
        try:
            response = await self._call_ai_api(prompt, "resume_tailoring")
            result = json.loads(response)
            
            # Store AI interaction
            await self._store_ai_interaction("resume_tailoring", prompt, response, None)
            
            return result
        except Exception as e:
            logger.error(f"Resume tailoring failed: {e}")
            return self._fallback_resume_tailoring()

    async def generate_ats_preview(self, resume_content: Dict) -> Dict[str, Any]:
        """
        Generate ATS preview showing how ATS will likely parse the resume
        """
        prompt = f"""
        You are simulating how an Applicant Tracking System (ATS) would parse this resume. 
        Show exactly what data the ATS would extract and any potential parsing issues.

        Resume Data:
        {json.dumps(resume_content, indent=2)}

        Provide a JSON response simulating ATS extraction:
        {{
            "parsed_data": {{
                "candidate_name": "Extracted name",
                "contact_email": "Extracted email",
                "contact_phone": "Extracted phone",
                "skills_extracted": ["List of skills ATS identified"],
                "experience_years": "Number if calculable",
                "education_level": "Highest degree found",
                "previous_companies": ["List of companies"],
                "job_titles": ["List of titles"]
            }},
            "parsing_confidence": 0.9,  // 0-1 how well ATS can parse this
            "potential_issues": [
                "Any formatting or content issues that might confuse ATS"
            ],
            "missing_sections": [
                "Standard sections that might be expected but missing"
            ],
            "optimization_tips": [
                "Specific suggestions to improve ATS compatibility"
            ]
        }}

        Be realistic about ATS limitations and common parsing failures.
        """
        
        try:
            response = await self._call_ai_api(prompt, "ats_preview")
            result = json.loads(response)
            
            await self._store_ai_interaction("ats_preview", prompt, response, None)
            
            return result
        except Exception as e:
            logger.error(f"ATS preview generation failed: {e}")
            return self._fallback_ats_preview()

    async def _call_ai_api(self, prompt: str, interaction_type: str) -> str:
        """Make API call to OpenAI-compatible endpoint (local or hosted)"""
        use_local = self.base_url.startswith("http://localhost") or \
                    self.base_url.startswith("https://localhost") or \
                    "host.docker.internal" in self.base_url
        if not self.api_key and not use_local:
            raise ValueError("No API key configured")
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert career advisor and resume specialist. Always provide valid JSON responses."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"API call failed: {response.status_code} {response.text}")
                
            result = response.json()
            return result["choices"][0]["message"]["content"]

    async def _store_ai_interaction(self, interaction_type: str, prompt: str, response: str, job_id: Optional[str]):
        """Store AI interaction for learning and cost tracking"""
        try:
            db = SessionLocal()
            interaction = AIInteraction(
                job_id=job_id,
                interaction_type=interaction_type,
                prompt=prompt,
                response=response,
                model_used=self.model
            )
            db.add(interaction)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Failed to store AI interaction: {e}")

    def _fallback_job_analysis(self) -> Dict[str, Any]:
        """Fallback analysis when AI fails"""
        return {
            "key_requirements": ["Unable to analyze - AI service unavailable"],
            "salary_range": None,
            "remote_policy": None,
            "difficulty_score": 0.5,
            "match_score": 0.5,
            "missing_skills": [],
            "competitive_advantages": [],
            "improvement_suggestions": ["Please try again - AI analysis failed"],
            "ats_keywords": [],
            "company_insights": "Analysis unavailable"
        }

    def _fallback_resume_tailoring(self) -> Dict[str, Any]:
        """Fallback when resume tailoring fails"""
        return {
            "tailored_resume": {},
            "changes_explanation": "Resume tailoring failed - AI service unavailable",
            "ats_score": 0.0,
            "keyword_integration": [],
            "improvement_suggestions": ["Please try again with AI service available"]
        }

    def _fallback_ats_preview(self) -> Dict[str, Any]:
        """Fallback when ATS preview fails"""
        return {
            "parsed_data": {},
            "parsing_confidence": 0.0,
            "potential_issues": ["ATS preview unavailable - AI service failed"],
            "missing_sections": [],
            "optimization_tips": ["Please try again with AI service available"]
        }


# Utility function to get AI service instance
def get_ai_service(user_api_key: Optional[str] = None, model: str = "gpt-5") -> AIService:
    """Get AI service instance with user's API key or system default"""
    return AIService(api_key=user_api_key, model=model)
