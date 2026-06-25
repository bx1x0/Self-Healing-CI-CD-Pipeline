import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

OPENMODEL_API_KEY = os.getenv("OPENMODEL_API_KEY")


def diagnose_failure(logs: str, run_info: dict) -> dict:
    prompt = f"""
You are a DevOps expert. A CI/CD pipeline has failed.

Workflow: {run_info['workflow_name']}
Branch: {run_info['branch']}
Commit: {run_info['commit']}

Logs:
{logs}

Respond ONLY in this JSON format, no extra text:
{{
  "failure_type": "flaky_test | dependency_error | syntax_error | env_missing | other",
  "root_cause": "one sentence explanation",
  "suggested_fix": "exact fix to apply",
  "auto_fixable": true or false
}}
"""

    response = requests.post(
        "https://console.openmodel.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENMODEL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        },
        timeout=60,
    )
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"]
    clean = raw.strip().replace("```json", "").replace("```", "")
    return json.loads(clean)
