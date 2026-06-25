import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def retry_pipeline(repo: str, run_id: int) -> None:
    """Re-run only the failed jobs for a workflow run."""
    if not GITHUB_TOKEN or GITHUB_TOKEN == "your_github_token":
        print("No GitHub token configured, skipping pipeline retry.")
        return

    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/rerun-failed-jobs"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    try:
        response = requests.post(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        print(f"Pipeline retry request failed: {exc}")
        return

    if response.status_code == 201:
        print("Pipeline retried successfully.")
    else:
        print(f"Retry failed: {response.status_code} {response.text}")


def send_slack_alert(info: dict, diagnosis: dict) -> None:
    """Send the AI diagnosis to Slack."""
    if not SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL == "your_slack_webhook_url":
        print("No Slack webhook configured, skipping Slack alert.")
        return

    message = {
        "text": f"""
Pipeline Failed!
Workflow: {info['workflow_name']}
Branch: {info['branch']}
Commit: {info['commit']}
Run URL: {info['run_url']}

AI Diagnosis:
- Type: {diagnosis['failure_type']}
- Root Cause: {diagnosis['root_cause']}
- Suggested Fix: {diagnosis['suggested_fix']}
- Auto-fixable: {diagnosis['auto_fixable']}
"""
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=30)
    except requests.RequestException as exc:
        print(f"Slack alert request failed: {exc}")
        return

    if response.status_code == 200:
        print("Slack alert sent.")
    else:
        print(f"Slack alert failed: {response.status_code} {response.text}")


def send_success_alert(info: dict) -> None:
    """Send a Slack notification when the pipeline succeeds."""
    if not SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL == "your_slack_webhook_url":
        print("No Slack webhook configured, skipping success alert.")
        return

    message = {
        "text": f"""
Pipeline Succeeded!
Workflow: {info['workflow_name']}
Branch: {info['branch']}
Commit: {info['commit']}
Run URL: {info['run_url']}

All checks passed successfully.
"""
    }

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=30)
    except requests.RequestException as exc:
        print(f"Slack success alert request failed: {exc}")
        return

    if response.status_code == 200:
        print("Slack success alert sent.")
    else:
        print(f"Slack success alert failed: {response.status_code} {response.text}")


def create_fix_pr(repo: str, info: dict, diagnosis: dict) -> None:
    """Create a PR branch and open a PR describing the suggested fix."""
    if not diagnosis.get("auto_fixable"):
        print("Not auto-fixable, skipping PR creation.")
        return

    if not GITHUB_TOKEN or GITHUB_TOKEN == "your_github_token":
        print("No GitHub token configured, skipping PR creation.")
        return

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    try:
        branch_url = f"https://api.github.com/repos/{repo}/git/ref/heads/{info['branch']}"
        branch_response = requests.get(branch_url, headers=headers, timeout=30)
        branch_response.raise_for_status()
        sha = branch_response.json()["object"]["sha"]

        fix_branch = f"auto-fix/{info['commit']}"
        ref_response = requests.post(
            f"https://api.github.com/repos/{repo}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{fix_branch}", "sha": sha},
            timeout=30,
        )

        if ref_response.status_code not in (201, 422):
            print(f"Fix branch creation failed: {ref_response.status_code} {ref_response.text}")
            return

        pr_response = requests.post(
            f"https://api.github.com/repos/{repo}/pulls",
            headers=headers,
            json={
                "title": f"Auto-fix: {diagnosis['failure_type']} on {info['branch']}",
                "body": f"""## AI-Generated Fix

**Root Cause:** {diagnosis['root_cause']}

**Suggested Fix:** {diagnosis['suggested_fix']}

**Commit:** {info['commit']}
**Run:** {info['run_url']}

> This PR was automatically created by the self-healing CI/CD pipeline.
""",
                "head": fix_branch,
                "base": info["branch"],
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"PR creation request failed: {exc}")
        return

    if pr_response.status_code == 201:
        pr_url = pr_response.json().get("html_url")
        print(f"Fix PR created: {pr_url}")
    elif pr_response.status_code == 422:
        print("Fix PR may already exist, skipping duplicate PR creation.")
    else:
        print(f"PR creation failed: {pr_response.status_code} {pr_response.text}")
