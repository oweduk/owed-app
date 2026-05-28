import json
import os
import sys
import datetime
import time
import base64
import urllib.request
import urllib.error
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq

GITHUB_PAT = os.environ.get("GH_PAT")
REPO = "oweduk/owed-app"
GITHUB_API = "https://api.github.com"
MEMORY_PATH = "memory/store.json"

def github_request(path, method="GET", data=None):
    url = f"{GITHUB_API}{path}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_PAT}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "OwedMetaProgrammer/1.0",
            "Content-Type": "application/json"
        },
        method=method
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))

def get_log_text(logs_url):
    req = urllib.request.Request(
        logs_url,
        headers={
            "Authorization": f"Bearer {GITHUB_PAT}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "OwedMetaProgrammer/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Could not fetch logs: {e}"

def get_file_content(filepath):
    data = github_request(f"/repos/{REPO}/contents/{filepath}")
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]

def commit_file(filepath, new_content, sha, message):
    encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
    github_request(
        f"/repos/{REPO}/contents/{filepath}",
        method="PUT",
        data={
            "message": message,
            "content": encoded,
            "sha": sha
        }
    )

def read_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)

def write_memory(memory):
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def run():
    timestamp = datetime.datetime.utcnow().isoformat()
    print(f"\n=== META-PROGRAMMER — {timestamp} ===")

    memory = read_memory()

    # Get recent workflow runs
    runs_data = github_request(f"/repos/{REPO}/actions/runs?per_page=10")
    runs = runs_data.get("workflow_runs", [])

    # Find the most recent failed run
    failed_run = None
    for run in runs:
        if run["conclusion"] == "failure":
            failed_run = run
            break

    if not failed_run:
        print("No failed runs found. System is clean.")
        return

    run_id = failed_run["id"]
    print(f"Failed run found: #{run_id} — {failed_run['display_title']}")

    # Get jobs for that run
    jobs_data = github_request(f"/repos/{REPO}/actions/runs/{run_id}/jobs")
    jobs = jobs_data.get("jobs", [])

    # Find the failed job
    failed_job = None
    for job in jobs:
        if job["conclusion"] == "failure":
            failed_job = job
            break

    if not failed_job:
        print("Could not identify failed job.")
        return

    print(f"Failed job: {failed_job['name']}")

    # Get logs
    job_id = failed_job["id"]
    logs_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}/logs"
    log_text = get_log_text(logs_url)
    log_tail = log_text[-4000:] if len(log_text) > 4000 else log_text

    # Extract failed filename from logs
    system_prompt = """You are a Python debugging expert. You will be given GitHub Actions log output from a failed workflow run.

Your job:
1. Identify exactly which Python file caused the failure (e.g. agents/content_agent.py)
2. Identify the exact error — type, line number, and cause
3. Read the file content provided and produce a complete fixed version
4. Return ONLY valid JSON in this exact structure:
{
  "failed_file": "agents/example.py",
  "error_type": "NameError/SyntaxError/etc",
  "error_summary": "one sentence description of the bug",
  "fix_description": "one sentence description of the fix applied",
  "fixed_code": "complete fixed Python file content"
}

Rules:
- Never truncate the fixed_code — return the entire file
- Never break existing logic — only fix the identified error
- If you cannot determine the file or fix with confidence, set failed_file to null"""

    user_message = f"""Log output (last 4000 chars):
{log_tail}"""

    print("Analysing failure...")
    response = call_groq(system_prompt, user_message, max_tokens=4000, temperature=0.2)

    try:
        diagnosis = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        diagnosis = json.loads(response[start:end])

    failed_file = diagnosis.get("failed_file")
    if not failed_file:
        print("Meta-programmer could not identify the broken file. Skipping.")
        return

    print(f"Diagnosed: {diagnosis.get('error_type')} in {failed_file}")
    print(f"Error: {diagnosis.get('error_summary')}")
    print(f"Fix: {diagnosis.get('fix_description')}")

    fixed_code = diagnosis.get("fixed_code", "")
    if not fixed_code.strip():
        print("No fixed code generated. Skipping.")
        return

    # Get current file SHA for commit
    _, sha = get_file_content(failed_file)

    # Commit the fix
    commit_message = f"[meta-programmer] Fix {diagnosis.get('error_type')} in {failed_file} — {diagnosis.get('fix_description')}"
    commit_file(failed_file, fixed_code, sha, commit_message)
    print(f"Fix committed: {commit_message}")

    # Log to memory
    if "meta_programmer_log" not in memory:
        memory["meta_programmer_log"] = []

    memory["meta_programmer_log"].append({
        "timestamp": timestamp,
        "run_id": run_id,
        "failed_file": failed_file,
        "error_type": diagnosis.get("error_type"),
        "error_summary": diagnosis.get("error_summary"),
        "fix_description": diagnosis.get("fix_description"),
        "committed": True
    })

    write_memory(memory)
    print("\nMeta-programmer cycle complete.")

if __name__ == "__main__":
    run()
