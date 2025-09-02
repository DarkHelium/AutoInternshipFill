import json
from typing import Any, Dict, Optional

from agents import Agent, Runner


async def tailor_resume_with_agent(
    job_analysis: Dict[str, Any],
    user_resume: str,
    user_constraints: Optional[Dict[str, Any]] = None,
    *,
    model: str = "gpt-5",
) -> Dict[str, Any]:
    """
    Generate a tailored resume JSON using the openai-agents library.

    This function relies on the `OPENAI_API_KEY` environment variable for
    authentication with the OpenAI API.

    Returns a dict with keys: tailored_resume, changes_explanation, ats_score,
    keyword_integration, improvement_suggestions.
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

Provide a STRICT JSON response with:
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
  "ats_score": 0.85,
  "keyword_integration": ["List of job keywords successfully integrated"],
  "improvement_suggestions": ["Additional suggestions for strengthening the application"]
}}

Return only JSON. Do not include any commentary.
"""

    agent = Agent(
        name="ResumeTailor",
        instructions="You are an expert resume writer, ATS optimization specialist, and career advisor. Always return valid JSON.",
        model=model,
    )

    result = await Runner.run(agent, prompt)

    if not result.final_output:
        return {"error": "Agent returned no output"}

    try:
        # The final_output might be a string that needs to be parsed into JSON
        if isinstance(result.final_output, str):
            return json.loads(result.final_output)
        elif isinstance(result.final_output, dict):
            return result.final_output
        else:
            return {
                "error": "Unexpected output type from agent",
                "output": str(result.final_output),
            }
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse JSON from agent output",
            "output": result.final_output,
        }

