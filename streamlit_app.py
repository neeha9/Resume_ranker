import os

import groq
import pandas as pd
import streamlit as st

from resume_ranker.emails import draft_interview_email
from resume_ranker.extract import extract_text
from resume_ranker.pii import redact_pii
from resume_ranker.ranking import evaluate_resume

MAX_RESUMES = 5

st.set_page_config(
    page_title="Resume ranker",
    page_icon=":material/fact_check:",
    layout="wide",
)


def get_api_key() -> str | None:
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY")


@st.cache_resource
def get_client(api_key: str | None) -> groq.Groq:
    return groq.Groq(api_key=api_key) if api_key else groq.Groq()


st.title("Resume ranker")
st.caption(
    "Paste a job description, upload candidate resumes, and get an AI-ranked "
    "shortlist. Phone numbers, emails, and mailing addresses are stripped out "
    "of every resume before anything is sent to Groq."
)

with st.sidebar:
    st.subheader("Email draft details")
    role_title = st.text_input(
        "Role title", key="role_title", placeholder="e.g. Senior Backend Engineer"
    )
    company_name = st.text_input("Company name", key="company_name", placeholder="Optional")
    sender_name = st.text_input(
        "Your name (email sign-off)", key="sender_name", placeholder="Optional"
    )

    st.divider()
    api_key = get_api_key()
    if api_key:
        st.success("Groq API key detected.", icon=":material/check_circle:")
    else:
        st.warning(
            "No Groq API key found. Add `GROQ_API_KEY` to "
            "`.streamlit/secrets.toml` or set it as an environment variable "
            "before ranking resumes.",
            icon=":material/key_off:",
        )

with st.form("intake_form", border=False):
    job_description = st.text_area(
        "Job description",
        height=240,
        placeholder="Paste the full job description here...",
        key="job_description",
    )
    resume_files = st.file_uploader(
        "Resumes",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="resume_uploader",
        help=f"Upload up to {MAX_RESUMES} resumes (PDF, DOCX, or TXT).",
    )
    submitted = st.form_submit_button(
        "Rank resumes", icon=":material/analytics:", type="primary"
    )

if submitted:
    if not job_description.strip():
        st.warning("Paste a job description before ranking.")
    elif not resume_files:
        st.warning("Upload at least one resume.")
    elif len(resume_files) > MAX_RESUMES:
        st.warning(f"Upload at most {MAX_RESUMES} resumes (found {len(resume_files)}).")
    elif not api_key:
        st.error(
            "No Groq API key configured. Add it in `.streamlit/secrets.toml` "
            "or as the `GROQ_API_KEY` environment variable, then try again."
        )
    else:
        client = get_client(api_key)
        results = []
        stop_early = False

        with st.status("Scoring resumes...", expanded=True) as status:
            for i, file in enumerate(resume_files):
                if stop_early:
                    break

                status.write(f"Reading {file.name}...")
                try:
                    raw_text = extract_text(file.name, file.getvalue())
                except ValueError as e:
                    status.write(f"Skipped {file.name}: {e}")
                    results.append({"id": i, "file": file.name, "error": str(e)})
                    continue

                redaction = redact_pii(raw_text)
                status.write(
                    f"Redacted {redaction.total} contact detail(s) from "
                    f"{file.name}, scoring against the job description..."
                )
                try:
                    evaluation = evaluate_resume(client, job_description, redaction.text)
                except groq.AuthenticationError:
                    status.write("Groq rejected the API key.")
                    st.error("The configured Groq API key was rejected. Check your credentials.")
                    stop_early = True
                    continue
                except groq.RateLimitError as e:
                    status.write(f"Rate limited on {file.name}: {e}")
                    results.append({"id": i, "file": file.name, "error": "Rate limited, try again shortly."})
                    continue
                except groq.APIStatusError as e:
                    status.write(f"Groq error on {file.name}: {e.message}")
                    results.append({"id": i, "file": file.name, "error": e.message})
                    continue
                except groq.APIConnectionError as e:
                    status.write(f"Network error on {file.name}: {e}")
                    results.append({"id": i, "file": file.name, "error": "Network error contacting Groq."})
                    continue

                results.append(
                    {
                        "id": i,
                        "file": file.name,
                        "candidate_name": file.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " "),
                        "score": evaluation.match_score,
                        "recommendation": evaluation.recommendation,
                        "summary": evaluation.summary,
                        "strengths": evaluation.strengths,
                        "gaps": evaluation.gaps,
                        "redacted_count": redaction.total,
                        "error": None,
                    }
                )

            status.update(
                label="Stopped early" if stop_early else "Done",
                state="error" if stop_early else "complete",
                expanded=stop_early,
            )

        st.session_state["ranking_results"] = results

if "ranking_results" in st.session_state:
    results = st.session_state["ranking_results"]
    ok_results = [r for r in results if not r.get("error")]
    failed_results = [r for r in results if r.get("error")]

    if failed_results:
        with st.expander(
            f"{len(failed_results)} resume(s) could not be scored", icon=":material/error:"
        ):
            for r in failed_results:
                st.write(f"**{r['file']}** — {r['error']}")

    if ok_results:
        st.subheader("Ranked candidates")

        df = pd.DataFrame(ok_results).sort_values("score", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", df.index + 1)

        edited = st.data_editor(
            df,
            width="stretch",
            column_order=["rank", "candidate_name", "score", "recommendation"],
            column_config={
                "id": None,
                "file": None,
                "error": None,
                "strengths": None,
                "gaps": None,
                "summary": None,
                "redacted_count": None,
                "rank": st.column_config.NumberColumn("Rank", width="small"),
                "candidate_name": st.column_config.TextColumn(
                    "Candidate", help="Edit to match the name on file", width="large"
                ),
                "score": st.column_config.ProgressColumn(
                    "Match score", min_value=0, max_value=100, format="%d", width="medium"
                ),
                "recommendation": st.column_config.TextColumn(
                    "Recommendation", width="medium"
                ),
            },
            disabled=["rank", "score", "recommendation"],
            hide_index=True,
            key="results_editor",
        )

        name_by_id = dict(zip(edited["id"], edited["candidate_name"]))

        st.subheader("Candidate detail")
        for _, row in df.iterrows():
            candidate_name = name_by_id.get(row["id"], row["candidate_name"])
            score = int(row["score"])
            with st.container(border=True):
                head_l, head_r = st.columns([3, 1], vertical_alignment="center")
                with head_l:
                    st.markdown(f"### {int(row['rank'])}. {candidate_name}")
                with head_r:
                    st.markdown(
                        f"<div style='text-align:right'><span style='font-size:1.6rem;"
                        f"font-weight:700'>{score}%</span><br>"
                        f"<span style='color:#2E5EAA;font-weight:600'>{row['recommendation']}</span></div>",
                        unsafe_allow_html=True,
                    )
                st.progress(score / 100, text=f"{score}% match")
                st.write(row["summary"])
                left, right = st.columns(2)
                with left:
                    st.markdown("**Strengths**")
                    for s in row["strengths"]:
                        st.markdown(f"- {s}")
                with right:
                    st.markdown("**Gaps**")
                    for g in row["gaps"]:
                        st.markdown(f"- {g}")
                st.caption(
                    f":material/shield: {row['redacted_count']} contact detail(s) "
                    "redacted before scoring"
                )

        st.subheader("Interview email drafts")
        st.caption(
            "Drafts are generated locally from the fields in the sidebar — "
            "no candidate data is sent to Groq for this step. Review and "
            "send them yourself once you've decided who to interview."
        )
        ordered_names = [name_by_id.get(row["id"], row["candidate_name"]) for _, row in df.iterrows()]
        default_picks = ordered_names[: min(3, len(ordered_names))]
        selected = st.multiselect(
            "Generate drafts for", options=ordered_names, default=default_picks
        )
        for name in selected:
            email_text = draft_interview_email(name, role_title, company_name, sender_name)
            with st.expander(name):
                st.code(email_text, language=None)
