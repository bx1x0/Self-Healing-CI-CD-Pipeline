def extract_failure_info(run: dict) -> dict:
    return {
        "workflow_name": run.get("name"),
        "branch": run.get("head_branch"),
        "commit": run.get("head_sha", "")[:7],
        "run_id": run.get("id"),
        "run_url": run.get("html_url"),
        "repo": run.get("repository", {}).get("full_name"),
    }
