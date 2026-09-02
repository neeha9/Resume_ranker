# Resume ranker

A Streamlit app for HR screening: paste a job description, upload candidate
resumes, and get an AI-ranked shortlist with per-candidate strengths and gaps.
Contact details are stripped from every resume before anything is sent to the
language model.

## How it works

1. **Extract** — `resume_ranker/extract.py` pulls plain text from each uploaded
   PDF, DOCX, or TXT file.
2. **Redact** — `resume_ranker/pii.py` removes email addresses, phone numbers,
   and physical addresses, replacing them with `[… redacted]` placeholders.
   Names, employers, schools, and skills are kept because the ranking step
   needs them.
3. **Score** — `resume_ranker/ranking.py` sends the redacted text plus the job
   description to the model and gets back a structured evaluation
   (0–100 match score, recommendation, summary, strengths, gaps).
4. **Draft emails** — `resume_ranker/emails.py` builds interview-invite drafts
   locally from the sidebar fields. No candidate data is sent to the model for
   this step.

Results are shown as a ranked table plus a full detail card per candidate
(score, recommendation, summary, strengths, gaps) with nothing hidden behind
an expander.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### API key

The scoring step uses the Groq API. Provide a key one of two ways:

- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill
  in `GROQ_API_KEY` (this file is gitignored), or
- Set the `GROQ_API_KEY` environment variable.

The model is set in `resume_ranker/ranking.py` (`MODEL`).

## Run

```bash
streamlit run streamlit_app.py
```

Then open http://localhost:8501.

- Upload **1 to 5** resumes (`MAX_RESUMES` in `streamlit_app.py`).
- The sidebar shows whether an API key was detected and holds the fields used
  for interview-email drafts.

## Privacy notes

- The full resume text (including PII) is read into server memory during
  processing, then discarded. It is not written to disk or logged.
- Redaction is regex-based and US-centric. It does **not** remove the
  candidate's name, LinkedIn/GitHub URLs, or non-US phone/address formats.
- The uploaded file's name is used as the candidate label in the UI but is not
  sent to the model.
