"""Local, template-based interview email drafts.

Generated entirely on-device from HR-provided fields - no candidate data is
sent to Claude for this step, since none of it needs AI judgment.
"""

from __future__ import annotations


def draft_interview_email(
    candidate_name: str,
    role_title: str,
    company_name: str,
    sender_name: str,
) -> str:
    role = role_title.strip() or "this position"
    company = f" at {company_name.strip()}" if company_name.strip() else ""
    sender = sender_name.strip() or "[Your name]"

    return f"""\
Subject: Interview invitation - {role}{company}

Hi {candidate_name},

Thank you for applying for the {role} role{company}. After reviewing your \
application, we'd like to invite you to the next step in our interview \
process.

Could you share a few times over the next week that would work for a \
30-minute conversation? We'll follow up with the details once we've found \
a time that fits your schedule.

Looking forward to speaking with you.

Best regards,
{sender}
"""
