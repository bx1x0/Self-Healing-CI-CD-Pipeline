import hashlib
import hmac
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

try:
    from webhook.ai_diagnosis import diagnose_failure
    from webhook.log_extractor import extract_failure_info
    from webhook.log_fetcher import fetch_run_logs
except ModuleNotFoundError:
    from ai_diagnosis import diagnose_failure
    from log_extractor import extract_failure_info
    from log_fetcher import fetch_run_logs

load_dotenv(Path(__file__).with_name(".env"))

app = FastAPI()
SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def github_webhook(request: Request):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify that the request really came from GitHub.
    if SECRET and not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = request.headers.get("X-GitHub-Event")

    # Only process completed workflow runs that failed.
    if event == "workflow_run" and payload.get("action") == "completed":
        run = payload["workflow_run"]
        if run["conclusion"] == "failure":
            info = extract_failure_info(run)
            print(f"Failure detected: {info['workflow_name']} on {info['branch']}")

            try:
                # Fetch real logs from GitHub.
                logs = fetch_run_logs(info["repo"], info["run_id"])

                if not logs.strip():
                    print("No failed job logs were found for this workflow run.")
                    return {"status": "received", "message": "no failed logs found"}

                # Send logs to OpenModel AI for diagnosis.
                diagnosis = diagnose_failure(logs, info)

                print("AI diagnosis:")
                print(json.dumps(diagnosis, indent=2))
            except Exception as exc:
                print(f"Webhook processing error: {exc}")
                return {"status": "received", "error": str(exc)}

    return {"status": "received"}
