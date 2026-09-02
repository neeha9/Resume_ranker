"""Score a (PII-redacted) resume against a job description using Groq."""

from __future__ import annotations

import json
from typing import Literal

from groq import Groq
from pydantic import BaseModel, Field, ValidationError

MODEL = "openai/gpt-oss-120b"

_SYSTEM_PROMPT = """\
You are helping an HR team screen job applicants. You will be given a job \
description and the text of one candidate's resume. Contact details (email, \
phone, mailing address) have already been stripped from the resume before it \
reached you - do not comment on their absence or attempt to infer them.

Judge the candidate strictly on how well their skills, experience, and \
qualifications match the job description. Be objective and evidence-based: \
cite concrete things from the resume, not assumptions about the person. \
Do not factor in anything related to the candidate's name, gender, ethnicity, \
age, or any other protected characteristic that might be implied by wording \
or formatting - if the resume text contains a name, ignore it entirely for \
scoring purposes.

Respond with a single JSON object and nothing else, matching this shape:
{
  "match_score": <integer 0-100, overall fit for the role>,
  "recommendation": <one of "Strong fit", "Good fit", "Possible fit", "Not a fit">,
  "summary": <one or two sentence overview of the fit>,
  "strengths": [<concrete matches to the job description>],
  "gaps": [<concrete mismatches or missing requirements>]
}
"""


class ResumeEvaluation(BaseModel):
    match_score: int = Field(
        ge=0, le=100, description="Overall fit for the role, 0-100."
    )
    recommendation: Literal["Strong fit", "Good fit", "Possible fit", "Not a fit"]
    summary: str = Field(description="One or two sentence overview of the fit.")
    strengths: list[str] = Field(description="Concrete matches to the job description.")
    gaps: list[str] = Field(description="Concrete mismatches or missing requirements.")


def evaluate_resume(
    client: Groq,
    job_description: str,
    redacted_resume_text: str,
) -> ResumeEvaluation:
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Job description:\n{job_description}\n\n"
                    f"Candidate resume (contact info redacted):\n{redacted_resume_text}"
                ),
            },
        ],
    )
    raw = response.choices[0].message.content or ""
    try:
        return ResumeEvaluation.model_validate_json(raw)
    except ValidationError:
        # Some models wrap the object in prose or code fences; recover the JSON.
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return ResumeEvaluation.model_validate(json.loads(raw[start : end + 1]))
        raise
