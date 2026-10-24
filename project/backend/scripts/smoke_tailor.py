"""Manual smoke check for resume_tailor against live AWS (Bedrock, DynamoDB, S3).

Not part of the automated suite. It calls paid AWS services.

Usage:
    uv run python scripts/smoke_tailor.py <user_id> <job_id>

The profile below is synthetic sample data.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.resume_tailor import tailor_resume_for_job

PERSONAL_INFO = {
    "name": "Asha Example",
    "email": "asha@example.com",
    "phone": "+91-90000-00000",
    "linkedin": "https://linkedin.com/in/asha-example",
    "github": "https://github.com/asha-example",
    "website": "https://asha-example.dev",
}

EDUCATION = [
    {
        "school": "Example Institute of Technology",
        "degree": "Bachelor of Technology",
        "field": "Computer Science",
        "dates": "Aug 2022 -- May 2026",
        "gpa": "CGPA - 8.70",
    },
]

EXPERIENCE = [
    {
        "title": "Software Engineer Intern",
        "company": "Sample Labs",
        "dates": "Jun 2025 -- Aug 2025",
        "highlights": [
            "Built FastAPI endpoints for model serving that handled 10K requests a day",
            "Containerised three services with Docker and deployed them on Kubernetes",
            "Added a GitHub Actions pipeline that cut deploy time from 20 to 8 minutes",
        ],
    },
]

SKILLS = [
    "Python",
    "TypeScript",
    "SQL",
    "FastAPI",
    "React",
    "Next.js",
    "AWS",
    "Docker",
    "Kubernetes",
    "PostgreSQL",
    "GitHub Actions",
]


async def main(user_id: str, job_id: str) -> None:
    print(f"Tailoring resume for job {job_id}...")
    result = await tailor_resume_for_job(
        user_id=user_id,
        job_id=job_id,
        personal_info=PERSONAL_INFO,
        education=EDUCATION,
        experience=EXPERIENCE,
        skills=SKILLS,
    )
    print(f"Resume ID: {result.resume_id}")
    print(f"PDF URL exists: {bool(result.pdf_url)}")
    print(f"Compilation error: {result.compilation_error}")
    print(f"Diff summary: {result.diff_summary}")

    with open("/tmp/tailor_test.tex", "w") as f:
        f.write(result.latex_content)
    print("Saved LaTeX to /tmp/tailor_test.tex")

    if result.pdf_url:
        print(f"PDF URL: {result.pdf_url[:80]}...")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: smoke_tailor.py <user_id> <job_id>")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
