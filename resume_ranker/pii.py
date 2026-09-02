"""Strip contact-identifying PII out of resume text before it is sent to Claude.

Only phone numbers, email addresses, and physical addresses are targeted -
everything else (name, skills, employers, education, links) is left intact
since the ranking step needs it to judge fit against the job description.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

_PHONE_RE = re.compile(
    r"""
    (?<!\d)
    (?:\+?\d{1,3}[-.\s]?)?          # optional country code
    (?:\(\d{3}\)|\d{3})             # area code, with or without parens
    [-.\s]?\d{3}[-.\s]?\d{4}        # local number
    (?:\s?(?:ext\.?|x)\s?\d{2,5})?  # optional extension
    (?!\d)
    """,
    re.VERBOSE | re.IGNORECASE,
)

_STREET_SUFFIXES = (
    r"Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Road|Rd|Court|Ct|"
    r"Circle|Cir|Way|Place|Pl|Terrace|Ter|Highway|Hwy|Parkway|Pkwy|Square|Sq|"
    r"Trail|Trl|Loop|Alley|Aly|Crossing|Xing"
)
_STREET_ADDRESS_RE = re.compile(
    rf"\d{{1,6}}\s+(?:[A-Za-z0-9.'\-]+\s+){{1,5}}(?:{_STREET_SUFFIXES})\.?"
    rf"(?:\s+(?:Apt|Suite|Ste|Unit|#)\.?\s*[A-Za-z0-9\-]+)?",
    re.IGNORECASE,
)

_CITY_STATE_ZIP_RE = re.compile(
    r"\b[A-Za-z][A-Za-z .'\-]{1,40},\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?\b"
)


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def redact_pii(text: str) -> RedactionResult:
    """Replace emails, phone numbers, and physical addresses with placeholders."""
    counts: dict[str, int] = {}

    text, n = _STREET_ADDRESS_RE.subn("[address redacted]", text)
    counts["address"] = n

    text, n = _CITY_STATE_ZIP_RE.subn("[address redacted]", text)
    counts["address"] += n

    text, n = _EMAIL_RE.subn("[email redacted]", text)
    counts["email"] = n

    text, n = _PHONE_RE.subn("[phone redacted]", text)
    counts["phone"] = n

    # Street + city/state/zip on the same line each match separately;
    # collapse the resulting run into a single placeholder.
    text = re.sub(
        r"\[address redacted\](?:[,\s]+\[address redacted\])+",
        "[address redacted]",
        text,
    )

    return RedactionResult(text=text, counts=counts)
