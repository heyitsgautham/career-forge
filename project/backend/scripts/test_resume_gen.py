#!/usr/bin/env python3.11
"""
CLI Resume Generation Test
==========================
Generates a resume using the full pipeline and saves output locally for inspection.
"""
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


USER_ID = "fd76cb4e-81e4-484f-9199-4b7239d8b173"


async def get_user_data():
    """Fetch user data from DynamoDB."""
    from app.services.dynamo_service import dynamo_service

    user = await dynamo_service.get_item("Users", {"userId": USER_ID})
    if not user:
        print(f"ERROR: No user found for {USER_ID}")
        sys.exit(1)

    user_id = user["userId"]
    personal_info = {
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "location": user.get("location", ""),
        "linkedin_url": user.get("linkedinUrl", ""),
        "website": user.get("website", ""),
        "github": user.get("githubUsername", ""),
    }

    def _parse_json(v):
        if not v:
            return []
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v if isinstance(v, list) else []

    education = _parse_json(user.get("education"))
    experience = _parse_json(user.get("experience"))
    skills = _parse_json(user.get("skills"))
    certifications = _parse_json(user.get("certifications"))

    print("=== USER DATA ===")
    print(f"  id: {user_id}")
    print(f"  name: {user.get('name')}")
    print(f"  email: {user.get('email')}")
    print(f"  phone: {user.get('phone')}")
    print(f"  education: {json.dumps(education, indent=2, default=str)}")
    print(f"  experience: {json.dumps(experience, indent=2, default=str)}")
    print(f"  skills: {json.dumps(skills, default=str)}")
    print()

    return user_id, personal_info, education, experience, skills, certifications


async def main():
    print("=" * 60)
    print("CAREER-FORGE RESUME GENERATION TEST")
    print("=" * 60)
    print()

    # 1. Get user data
    user_id, personal_info, education, experience, skills, certifications = await get_user_data()

    # 2. Generate resume
    from app.services.resume_agent import generate_resume_from_summaries, clear_analysis_cache

    # Clear cache to force fresh generation
    clear_analysis_cache()

    print("=== GENERATING RESUME ===")
    print("  Calling Claude for analysis + JSON generation...")
    print()

    try:
        result = await generate_resume_from_summaries(
            user_id=user_id,
            jd=None,  # No JD for base resume test
            personal_info=personal_info,
            education=education,
            experience=experience,
            skills=skills,
            certifications=certifications,
        )
    except Exception as e:
        print(f"GENERATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("=== GENERATION RESULT ===")
    print(f"  resume_id: {result.resume_id}")
    print(f"  pdf_url: {'YES' if result.pdf_url else 'NO'}")
    print(f"  tex_url: {'YES' if result.tex_url else 'NO'}")
    print(f"  compilation_error: {result.compilation_error or 'None'}")
    print()

    # 3. Save LaTeX locally
    tex_path = f"/tmp/test_resume.tex"
    with open(tex_path, "w") as f:
        f.write(result.latex_content)
    print(f"  LaTeX saved: {tex_path}")

    # 4. Save analysis 
    analysis_path = f"/tmp/test_resume_analysis.txt"
    with open(analysis_path, "w") as f:
        f.write(result.analysis)
    print(f"  Analysis saved: {analysis_path}")

    # 5. Try to find local PDF
    uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "pdfs")
    pdf_files = []
    if os.path.exists(uploads_dir):
        pdf_files = sorted(
            [f for f in os.listdir(uploads_dir) if f.endswith('.pdf')],
            key=lambda f: os.path.getmtime(os.path.join(uploads_dir, f)),
            reverse=True
        )

    if pdf_files:
        latest_pdf = os.path.join(uploads_dir, pdf_files[0])
        import shutil
        local_pdf = "/tmp/test_resume.pdf"
        shutil.copy2(latest_pdf, local_pdf)
        print(f"  PDF saved: {local_pdf}")
    else:
        print("  WARNING: No PDF found in uploads/pdfs/")

    # 6. Print LaTeX content for inspection
    print()
    print("=== LATEX CONTENT (first 3000 chars) ===")
    print(result.latex_content[:3000])
    print("..." if len(result.latex_content) > 3000 else "")
    print()

    # 7. Quality checks
    print("=== QUALITY CHECKS ===")
    latex = result.latex_content

    # Check sections present
    sections = ["Professional Summary", "Education", "Experience", "Projects", "Technical Skills"]
    for s in sections:
        present = s in latex
        print(f"  [{'+' if present else '-'}] Section: {s}")

    # Count resumeSubheading entries
    import re
    edu_count = len(re.findall(r"\\resumeSubheading", latex.split("Experience")[0] if "Experience" in latex else latex.split("Projects")[0]))
    print(f"  Education entries: {edu_count}")

    # Count project entries
    proj_section = ""
    if "Projects" in latex and "Technical Skills" in latex:
        proj_section = latex.split("Projects")[1].split("Technical Skills")[0]
    proj_count = len(re.findall(r"\\resumeProjectHeading", proj_section))
    print(f"  Project entries: {proj_count}")

    # Count bullets
    all_bullets = re.findall(r"\\resumeItem\{(.*?)\}", latex, re.DOTALL)
    print(f"  Total bullets: {len(all_bullets)}")

    # Check bullet lengths
    short_bullets = [b for b in all_bullets if len(b.strip()) < 85]
    long_bullets = [b for b in all_bullets if len(b.strip()) > 120]
    print(f"  Short bullets (<85 chars): {len(short_bullets)}")
    print(f"  Long bullets (>120 chars): {len(long_bullets)}")

    if short_bullets:
        print("  --- SHORT BULLETS ---")
        for b in short_bullets:
            print(f"    [{len(b.strip())} chars] {b.strip()[:100]}")

    if long_bullets:
        print("  --- LONG BULLETS ---")
        for b in long_bullets:
            print(f"    [{len(b.strip())} chars] {b.strip()[:100]}...")

    print()
    print("DONE. Check /tmp/test_resume.pdf for visual inspection.")


if __name__ == "__main__":
    asyncio.run(main())
