import json
import os
import sys
import datetime
import base64
import urllib.request
import urllib.error
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq, get_profile, evolve_profile

GH_PAT = os.environ.get("GH_PAT")
REPO = "oweduk/owed-app"
GITHUB_API = "https://api.github.com"
MEMORY_PATH = "memory/store.json"
MAX_AUTO_RERUNS = 3

def github_request(path, method="GET", data=None):
    url = f"{GITHUB_API}{path}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {GH_PAT}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "OwedWorkflowAuditor/1.0",
            "Content-Type": "application/json"
        },
        method=method
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))

def get_file(filepath):
    data = github_request(f"/repos/{REPO}/contents/{filepath}")
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]

def commit_file(filepath, content, sha, message):
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    github_request(
        f"/repos/{REPO}/contents/{filepath}",
        method="PUT",
        data={"message": message, "content": encoded, "sha": sha}
    )

def trigger_rerun(run_id):
    github_request(
        f"/repos/{REPO}/actions/runs/{run_id}/rerun",
        method="POST"
    )

def get_run_logs(job_id):
    logs_url = f"{GITHUB_API}/repos/{REPO}/actions/jobs/{job_id}/logs"
    req = urllib.request.Request(
        logs_url,
        headers={
            "Authorization": f"Bearer {GH_PAT}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "OwedWorkflowAuditor/1.0"
        }
    )
    try:
        # GitHub redirects to a presigned S3 URL — follow without auth header
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        class NoAuthOnRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                new_req = urllib.request.Request(newurl)
                new_req.add_header("User-Agent", "OwedWorkflowAuditor/1.0")
                return new_req
        opener = urllib.request.build_opener(NoAuthOnRedirect())
        with opener.open(req) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Could not fetch logs: {e}"

def read_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)

def write_memory(memory):
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def run():
    timestamp = datetime.datetime.utcnow().isoformat()
    print(f"\n=== WORKFLOW AUDITOR — {timestamp} ===")

    memory = read_memory()
    profile = get_profile("workflow_auditor")
    cycles = memory.get("cycles", 0)

    # Circuit breaker
    rerun_count = memory.get("rerun_count_this_cycle", 0)
    if rerun_count >= MAX_AUTO_RERUNS:
        print(f"Max auto-reruns ({MAX_AUTO_RERUNS}) reached this cycle — standing down.")
        memory["rerun_count_this_cycle"] = 0
        write_memory(memory)
        return

    # Get most recent workflow run
    runs_data = github_request(f"/repos/{REPO}/actions/runs?per_page=5")
    runs = runs_data.get("workflow_runs", [])
    if not runs:
        print("No runs found.")
        return

    latest_run = runs[0]
    run_id = latest_run["id"]
    conclusion = latest_run["conclusion"]

    print(f"Latest run: #{run_id} — conclusion: {conclusion}")

    # Get jobs
    jobs_data = github_request(f"/repos/{REPO}/actions/runs/{run_id}/jobs")
    jobs = jobs_data.get("jobs", [])

    # Collect all job logs — success and failure
    all_logs = ""
    for job in jobs:
        job_id = job["id"]
        job_name = job["name"]
        job_conclusion = job.get("conclusion", "unknown")
        log_text = get_run_logs(job_id)
        all_logs += f"\n--- {job_name} ({job_conclusion}) ---\n{log_text[-1000:]}\n"

    log_summary = all_logs[-3000:]

    system_prompt = f"""{profile}

You are a vicious, uncompromising workflow auditor. You read GitHub Actions logs and find every problem — errors, warnings, degraded outputs, inefficiencies, wasted steps, poor quality outputs — even in successful runs.

You respond in JSON:
{{
  "overall_verdict": "pass/warn/fail",
  "issues": [
    {{
      "severity": "critical/major/minor",
      "step": "which step has the issue",
      "description": "what is wrong",
      "file_to_fix": "agents/filename.py or null",
      "fix_description": "exactly what to change"
    }}
  ],
  "trigger_rerun": true/false,
  "rerun_reason": "why a rerun is needed or null",
  "audit_summary": "one brutal sentence on system state"
}}

Rules:
- trigger_rerun only if there are critical or major issues that were fixed
- Be specific — vague issues are useless
- A successful run with poor quality outputs is still a failure"""

    user_message = f"""Cycle: {cycles}
Run #{run_id} conclusion: {conclusion}
Rerun count this cycle: {rerun_count}

Logs:
{log_summary}

Audit brutally."""

    print("Auditing workflow...")
    response = call_groq(system_prompt, user_message, max_tokens=2000, temperature=0.3)

    if not response or not response.strip():
        print("Empty response — skipping.")
        return

    try:
        audit = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"Parse failed — skipping. Raw: {response[:200]}")
            return
        audit = json.loads(response[start:end])

    print(f"\nVerdict: {audit.get('overall_verdict', '?').upper()}")
    print(f"Summary: {audit.get('audit_summary', '')}")

    issues = audit.get("issues", [])
    for issue in issues:
        print(f"  [{issue.get('severity', '?').upper()}] {issue.get('step', '?')}: {issue.get('description', '')}")

    # Attempt fixes for issues with identified files
    fixes_committed = 0
    for issue in issues:
        filepath = issue.get("file_to_fix")
        fix_desc = issue.get("fix_description", "")
        severity = issue.get("severity", "minor")

        if not filepath or severity == "minor" or not fix_desc:
            continue

        try:
            current_code, sha = get_file(filepath)
        except Exception as e:
            print(f"Could not read {filepath}: {e}")
            continue

        fix_prompt = """You are a Python expert. You will receive a file and a description of what needs to change.
Return ONLY the complete fixed Python file. No explanation, no markdown fences."""

        fix_response = call_groq(
            fix_prompt,
            f"File ({filepath}):\n{current_code[:2000]}\n\nFix needed: {fix_desc}",
            max_tokens=2000,
            temperature=0.2
        )

        if not fix_response or len(fix_response) < 50:
            continue

        fix_response = fix_response.strip()
        if fix_response.startswith("```"):
            fix_response = fix_response.split("\n", 1)[-1]
            fix_response = fix_response.rsplit("```", 1)[0]

        commit_file(
            filepath,
            fix_response,
            sha,
            f"[workflow-auditor] Fix {severity} issue in {filepath}: {fix_desc[:80]}"
        )
        print(f"Fix committed for {filepath}")
        fixes_committed += 1

    # Trigger rerun if fixes were made and auditor recommends it
    if audit.get("trigger_rerun") and fixes_committed > 0:
        memory["rerun_count_this_cycle"] = rerun_count + 1
        write_memory(memory)
        trigger_rerun(run_id)
        print(f"Rerun triggered (rerun {rerun_count + 1}/{MAX_AUTO_RERUNS}). Reason: {audit.get('rerun_reason', '')}")
    else:
        memory["rerun_count_this_cycle"] = 0

    # Log audit
    if "audit_log" not in memory:
        memory["audit_log"] = []
    memory["audit_log"].append({
        "timestamp": timestamp,
        "cycle": cycles,
        "run_id": run_id,
        "verdict": audit.get("overall_verdict"),
        "issues_found": len(issues),
        "fixes_committed": fixes_committed,
        "rerun_triggered": audit.get("trigger_rerun") and fixes_committed > 0,
        "summary": audit.get("audit_summary", "")
    })

    write_memory(memory)
    evolve_profile("workflow_auditor", profile, f"Audited run #{run_id}. Verdict: {audit.get('overall_verdict')}. Issues: {len(issues)}. Fixes: {fixes_committed}.")
    print("\nWorkflow auditor cycle complete.")

if __name__ == "__main__":
    run()
