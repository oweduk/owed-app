import json
import os
import sys
import datetime
import base64
import urllib.request
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq, get_profile, evolve_profile

GH_PAT = os.environ.get("GH_PAT")
REPO = "oweduk/owed-app"
GITHUB_API = "https://api.github.com"
MEMORY_PATH = "memory/store.json"
WORKFLOW_PATH = ".github/workflows/orchestrator.yml"

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
            "User-Agent": "OwedWorkflowAgent/1.0",
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

def read_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)

def write_memory(memory):
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def run():
    timestamp = datetime.datetime.utcnow().isoformat()
    print(f"\n=== WORKFLOW AGENT — {timestamp} ===")

    memory = read_memory()
    profile = get_profile("workflow_agent")
    cycles = memory.get("cycles", 0)

    # Only evolve topology every 3 cycles — avoid thrashing
    if cycles % 3 != 0:
        print(f"Cycle {cycles} — topology evolution runs every 3 cycles. Skipping.")
        return

    agent_elo = memory.get("agent_elo", {})
    vigil_log = memory.get("vigil_log", [])[-3:]
    audit_log = memory.get("audit_log", [])[-3:]
    generated_agents = memory.get("generated_agents", [])

    # Read current workflow
    current_workflow, sha = get_file(WORKFLOW_PATH)

    system_prompt = f"""{profile}

You are a workflow topology engineer. You analyse agent performance data and evolve the GitHub Actions workflow to maximise system effectiveness.

You can:
- Reorder agents to improve data flow
- Add wait times between high-cost agents
- Remove or disable consistently underperforming agents
- Add newly generated agents that aren't yet in the workflow
- Adjust cron schedule if cycles are too frequent or infrequent

Rules — never violate:
- Never remove: checkout, setup-python, commit, push steps
- Never remove: meta_programmer, hyperagent, orchestrator, workflow_auditor
- Never change secrets or permissions blocks
- Always keep workflow_dispatch trigger
- Keep cron at 0 */6 * * * unless there is strong evidence to change it
- Any new agent step must include GROQ_API_KEY env var
- GH_PAT must be included for: meta_programmer, hyperagent, workflow_auditor, workflow_agent
- Return ONLY the complete updated YAML — no explanation, no markdown fences

Respond in JSON:
{{
  "topology_changes": "one sentence describing what you changed and why",
  "confidence": 1-10,
  "updated_yaml": "complete workflow yaml with \\n for newlines"
}}"""

    user_message = f"""Cycle: {cycles}
Agent ELO standings: {json.dumps(agent_elo, indent=2)}
VIGIL health summaries: {json.dumps([v.get('verdict', {}).get('overall_health', '') for v in vigil_log], indent=2)}
Audit verdicts: {json.dumps([a.get('verdict', '') for a in audit_log], indent=2)}
Recently generated agents: {json.dumps([a.get('name', '') for a in generated_agents[-3:]], indent=2)}

Current workflow:
{current_workflow[:3000]}

Analyse and evolve the topology."""

    print("Analysing workflow topology...")
    response = call_groq(system_prompt, user_message, max_tokens=3000, temperature=0.3)

    if not response or not response.strip():
        print("Empty response — skipping.")
        return

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"Parse failed — skipping.")
            return
        result = json.loads(response[start:end])

    confidence = result.get("confidence", 0)
    updated_yaml = result.get("updated_yaml", "")
    changes = result.get("topology_changes", "")

    print(f"Changes: {changes}")
    print(f"Confidence: {confidence}/10")

    if confidence < 7:
        print("Confidence too low — skipping commit to protect workflow.")
        return

    if "on:" not in updated_yaml or "jobs:" not in updated_yaml:
        print("Invalid YAML generated — skipping.")
        return

    updated_yaml = updated_yaml.replace("\\n", "\n")

    commit_file(
        WORKFLOW_PATH,
        updated_yaml,
        sha,
        f"[workflow-agent] Evolve topology — cycle {cycles}: {changes[:80]}"
    )
    print("Workflow topology updated and committed.")

    if "workflow_evolution_log" not in memory:
        memory["workflow_evolution_log"] = []

    memory["workflow_evolution_log"].append({
        "cycle": cycles,
        "timestamp": timestamp,
        "changes": changes,
        "confidence": confidence
    })

    write_memory(memory)
    evolve_profile("workflow_agent", profile, f"Evolved workflow topology at cycle {cycles}. Changes: {changes[:100]}")
    print("Workflow agent cycle complete.")

if __name__ == "__main__":
    run()
