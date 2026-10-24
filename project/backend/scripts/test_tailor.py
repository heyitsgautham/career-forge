"""Quick CLI test for resume_tailor with improved prompt."""

import asyncio
import sys

sys.path.insert(0, "/Users/gauthamkrishna/Projects/career-forge/project/backend")

from app.services.resume_tailor import tailor_resume_for_job


USER_ID = "fd76cb4e-81e4-484f-9199-4b7239d8b173"
JOB_ID = "2e3778d1-0b54-4185-9948-36ce54271dbb"  # Sprinklr Software Engineer

PERSONAL_INFO = {
    "name": "Gautham Krishna S",
    "email": "heyitsgautham@gmail.com",
    "phone": "+91-8825885520",
    "linkedin": "https://linkedin.com/in/heyitsgautham",
    "github": "https://github.com/heyitsgautham",
    "website": "https://heyitsgautham.github.io/portfolio",
}

EDUCATION = [
    {
        "school": "Indian Institute of Technology Madras",
        "degree": "Bachelor of Science",
        "field": "Data Science and Applications",
        "dates": "May 2023 -- May 2027",
        "gpa": "CGPA - 9.17",
    },
    {
        "school": "Saveetha Engineering College",
        "degree": "Bachelor of Technology",
        "field": "Artificial Intelligence and Machine Learning",
        "dates": "Sep 2023 -- May 2027",
        "gpa": "CGPA - 8.85",
    },
]

EXPERIENCE = [
    {
        "title": "Software Engineer Intern",
        "company": "Presidio",
        "dates": "Sep 2025 -- Nov 2025",
        "highlights": [
            "Developed RESTful APIs with FastAPI for ML model serving, handling 10K+ inference requests daily",
            "Implemented containerized microservices using Docker and Kubernetes for scalable AI deployments",
            "Built automated CI/CD pipelines with GitHub Actions, reducing deployment time by 60%",
            "Optimized PostgreSQL queries and implemented caching strategies, improving response time by 35%",
        ],
    },
    {
        "title": "Team Leader - AI Infrastructure",
        "company": "Google Cloud Platform, IIT Madras",
        "dates": "Oct 2024 -- Dec 2024",
        "highlights": [
            "Built ML training clusters on GKE with GPU node pools for distributed model training workflows",
            "Deployed model serving infrastructure on Vertex AI with auto-scaling endpoints, 99.5% availability",
            "Configured VPC networks, load balancers, and firewall rules for secure AI infrastructure",
            "Led 5-member team through 15+ labs on Kubernetes orchestration and distributed computing patterns",
        ],
    },
]

SKILLS = [
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "SQL",
    "C",
    "Bash",
    "PyTorch",
    "Transformers",
    "LangChain",
    "RAG",
    "Gemini",
    "ChromaDB",
    "FAISS",
    "FastAPI",
    "React",
    "Next.js",
    "Spark MLlib",
    "AWS",
    "GCP",
    "Vertex AI",
    "GKE",
    "Docker",
    "Kubernetes",
    "Git",
    "GitHub Actions",
    "Terraform",
    "Kafka",
    "PostgreSQL",
]


async def main():
    print(f"Tailoring resume for job {JOB_ID}...")
    result = await tailor_resume_for_job(
        user_id=USER_ID,
        job_id=JOB_ID,
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
    asyncio.run(main())
