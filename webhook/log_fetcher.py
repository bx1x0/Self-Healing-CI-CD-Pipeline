import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


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
            log_response = requests.get(
                log_url,
                headers=headers,
                allow_redirects=True,
                timeout=30,
            )
            log_response.raise_for_status()
            lines = log_response.text.splitlines()
            failed_logs.append(f"Job: {job['name']}\n" + "\n".join(lines[-100:]))

    return "\n\n".join(failed_logs)
