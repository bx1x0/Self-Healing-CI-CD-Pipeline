import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

OPENMODEL_API_KEY = os.getenv("OPENMODEL_API_KEY")


def fallback_diagnosis(logs: str) -> dict:
    lower_logs = logs.lower()

    if "assert" in lower_logs or "pytest" in lower_logs or "failed steps:" in lower_logs:
        return {
            "failure_type": "flaky_test",
            "root_cause": "A test failed during the CI pipeline.",
            "suggested_fix": "Open the failed test shown in the logs and update the expected value or application logic.",
            "auto_fixable": True,
        }

    if "modulenotfounderror" in lower_logs or "no module named" in lower_logs:
        return {
            "failure_type": "dependency_error",
            "root_cause": "Python could not import a required module during the pipeline run.",
            "suggested_fix": "Install the missing dependency or fix the import path.",
            "auto_fixable": True,
        }

    if "syntaxerror" in lower_logs:
        return {
            "failure_type": "syntax_error",
            "root_cause": "The pipeline failed because Python found invalid syntax.",
            "suggested_fix": "Fix the syntax error shown in the logs.",
            "auto_fixable": True,
        }

    return {
        "failure_type": "other",
        "root_cause": "The AI diagnosis service was unavailable, so only a basic local diagnosis was generated.",
        "suggested_fix": "Review the failed job logs and rerun the webhook when the AI service is reachable.",
        "auto_fixable": False,
    }


def diagnose_failure(logs: str, run_info: dict) -> dict:
    if not OPENMODEL_API_KEY or OPENMODEL_API_KEY == "your_openmodel_key":
        print("OPENMODEL_API_KEY is missing. Using local fallback diagnosis.")
        return fallback_diagnosis(logs)

    prompt = f"""
You are a DevOps expert. A CI/CD pipeline has failed.

Workflow: {run_info['workflow_name']}
Branch: {run_info['branch']}
Commit: {run_info['commit']}

Logs:
{logs}

Important:
- Diagnose the CI/CD pipeline failure, not webhook listener/network problems.
- If raw logs were unavailable to the webhook listener, do not classify that as the pipeline root cause.
- If only a failed pytest/test step summary is available, classify it as flaky_test and suggest checking/fixing the failing test assertion.

Respond ONLY in this JSON format, no extra text:
{{
  "failure_type": "flaky_test | dependency_error | syntax_error | env_missing | other",
  "root_cause": "one sentence explanation",
  "suggested_fix": "exact fix to apply",
  "auto_fixable": true or false
}}
"""

    try:
        response = requests.post(
            "https://api.openmodel.ai/v1/messages",
            headers={
                "Authorization": f"Bearer {OPENMODEL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        print(f"OpenModel API is unreachable. Using local fallback diagnosis: {exc}")
        return fallback_diagnosis(logs)

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        print(
            "OpenModel API request failed. "
            f"Using local fallback diagnosis: {response.status_code} {response.text}"
        )
        return fallback_diagnosis(logs)

    data = response.json()
    raw = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            raw = block.get("text", "")
            break

    clean = raw.strip().replace("```json", "").replace("```", "")
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        print("OpenModel returned invalid JSON. Using local fallback diagnosis.")
        return fallback_diagnosis(logs)
