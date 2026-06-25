import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def build_job_summary(job: dict, raw_logs_available: bool = True) -> str:
    lines = [
        f"Job: {job.get('name')}",
        f"Conclusion: {job.get('conclusion')}",
    ]

    if not raw_logs_available:
        lines.append(
            "Raw logs were not available to the webhook listener, "
            "so use the failed job/step summary below."
        )

    failed_steps = [
        step for step in job.get("steps", [])
        if step.get("conclusion") == "failure"
    ]

    if failed_steps:
        lines.append("Failed steps:")
        for step in failed_steps:
            lines.append(
                "- "
                f"{step.get('name')} "
                f"(status={step.get('status')}, conclusion={step.get('conclusion')}, "
                f"started={step.get('started_at')}, completed={step.get('completed_at')})"
            )
    else:
        lines.append("No failed step details were available from the Jobs API.")

    return "\n".join(lines)


def fetch_run_logs(repo: str, run_id: int) -> str:
    if not GITHUB_TOKEN or GITHUB_TOKEN == "your_github_token":
        raise ValueError("GITHUB_TOKEN is missing in webhook/.env")

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
    jobs_response = requests.get(jobs_url, headers=headers, timeout=30)
    jobs_response.raise_for_status()
    jobs = jobs_response.json()

    failed_logs = []

    for job in jobs.get("jobs", []):
        if job["conclusion"] == "failure":
            job_id = job["id"]
            log_url = f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs"
            try:
                log_response = requests.get(
                    log_url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=30,
                )
                log_response.raise_for_status()
                lines = log_response.text.splitlines()
                failed_logs.append(f"Job: {job['name']}\n" + "\n".join(lines[-100:]))
            except requests.RequestException as exc:
                print(f"Could not download raw logs for job {job['name']}: {exc}")
                failed_logs.append(build_job_summary(job, raw_logs_available=False))

    return "\n\n".join(failed_logs)
