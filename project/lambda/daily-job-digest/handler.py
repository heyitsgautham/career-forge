"""
daily-job-digest/handler.py
---------------------------
AWS Lambda — triggered nightly by EventBridge cron.
Scans the DynamoDB `Jobs` table, picks the top N jobs by matchScore,
formats a plain-text digest, and publishes it to an SNS Topic.
SNS delivers the email to all subscribed addresses.

Environment variables (set in Lambda console or SAM template):
  DYNAMODB_TABLE   — DynamoDB table name           (default: Jobs)
  SNS_TOPIC_ARN    — ARN of the SNS email topic    (required)
  TOP_JOBS_COUNT   — Number of top jobs to include (default: 5)
  AWS_REGION       — AWS region                    (default: us-east-1)
"""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

# ── env vars ────────────────────────────────────────────────────────────────
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "Jobs")
SNS_TOPIC_ARN  = os.environ.get("SNS_TOPIC_ARN", "")
TOP_N          = int(os.environ.get("TOP_JOBS_COUNT", "5"))
AWS_REGION     = os.environ.get("AWS_REGION", "us-east-1")


# ── helpers ──────────────────────────────────────────────────────────────────

def _to_float(value: Any) -> float:
    """Convert Decimal (DynamoDB) or string to float safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fetch_top_jobs(dynamodb_resource) -> list[dict]:
    """
    Scan the Jobs table, keep only records that have a matchScore,
    and return the top TOP_N sorted by matchScore descending.
    """
    table = dynamodb_resource.Table(DYNAMODB_TABLE)

    scan_kwargs: dict = {
        "FilterExpression": Attr("matchScore").exists(),
    }
    items: list[dict] = []

    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    # Sort by matchScore descending; Decimal-safe
    items.sort(key=lambda j: _to_float(j.get("matchScore", 0)), reverse=True)
    return items[:TOP_N]


def format_digest(jobs: list[dict]) -> tuple[str, str]:
    """Return (subject, body) for the SNS publish call."""
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"CareerForge Daily Job Digest — {today}"

    if not jobs:
        body = (
            f"CareerForge — Daily Job Digest\n"
            f"Date: {today}\n\n"
            "No scored jobs found yet. Run a Job Scout scan to populate your board!\n\n"
            "Open the CareerForge dashboard to get started."
        )
        return subject, body

    lines: list[str] = [
        "CareerForge — Daily Job Digest",
        f"Date        : {today}",
        f"Top {len(jobs)} jobs by match score",
        "=" * 52,
        "",
    ]

    for i, job in enumerate(jobs, 1):
        score    = _to_float(job.get("matchScore", 0))
        title    = job.get("title", "Unknown Title")
        company  = job.get("company", "Unknown Company")
        location = job.get("location", "Remote")
        url      = job.get("url", "")
        salary   = job.get("salary", "")
        job_type = job.get("jobType", "")

        # Top 5 required skills
        raw_skills = job.get("requiredSkills", [])
        if isinstance(raw_skills, list):
            skills_str = ", ".join(str(s) for s in raw_skills[:5]) or "N/A"
        else:
            skills_str = str(raw_skills)

        # Missing skills hint
        missing = job.get("missingSkills", [])
        if isinstance(missing, list) and missing:
            missing_str = ", ".join(str(s) for s in missing[:3])
        else:
            missing_str = ""

        lines.append(f"#{i}  {title}")
        lines.append(f"    Company     : {company}")
        lines.append(f"    Location    : {location}")
        lines.append(f"    Match Score : {score:.0f}%")
        if salary:
            lines.append(f"    Salary      : {salary}")
        if job_type:
            lines.append(f"    Type        : {job_type}")
        lines.append(f"    Skills      : {skills_str}")
        if missing_str:
            lines.append(f"    Gaps        : {missing_str}")
        if url:
            lines.append(f"    Apply       : {url}")
        lines.append("")

    lines += [
        "─" * 52,
        "View all matches in your CareerForge dashboard.",
        "Generate a tailored resume for any job with one click.",
        "",
        "You received this email because you subscribed to",
        "CareerForge daily job alerts.",
    ]

    return subject, "\n".join(lines)


# ── Lambda entry point ───────────────────────────────────────────────────────

def lambda_handler(event: dict, context: Any) -> dict:
    """
    Entry point invoked by EventBridge scheduled rule.
    event payload is ignored — digest always covers top N jobs overall.
    """
    if not SNS_TOPIC_ARN:
        raise EnvironmentError("SNS_TOPIC_ARN is not set. Cannot publish daily digest.")

    print(f"[daily-job-digest] region={AWS_REGION} table={DYNAMODB_TABLE} top_n={TOP_N}")

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    sns      = boto3.client("sns",        region_name=AWS_REGION)

    jobs = fetch_top_jobs(dynamodb)
    print(f"[daily-job-digest] Fetched {len(jobs)} scored jobs")

    subject, body = format_digest(jobs)
    print(f"[daily-job-digest] Publishing to SNS: subject='{subject}'")

    response = sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=subject,
        Message=body,
    )

    message_id = response.get("MessageId", "")
    print(f"[daily-job-digest] Published. MessageId={message_id}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message"  : "Daily digest published to SNS",
            "messageId": message_id,
            "jobCount" : len(jobs),
            "date"     : datetime.now(timezone.utc).isoformat(),
        }),
    }
