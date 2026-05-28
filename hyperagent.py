import json
import os
import sys
import datetime
import base64
import urllib.request
import urllib.error
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agents.utils import call_groq

GH_PAT = os.environ.get("GH_PAT")
REPO = "oweduk/owed-app"
GITHUB_API = "https://api.github.com"
MEMORY_PATH = "memory/store.json"
ORCHESTRATOR_PATH = "orchestrator/brain.py"

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
            "User-Agent": "OwedHyperagent/1.0",
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
    print(f"\n=== HYPERAGENT — {timestamp} ===")

    memory = read_memory()
    cycles = memory.get("cycles", 0)

    # Read current orchestrator code
    orchestrator_code, sha = get_file(ORCHESTRATOR_PATH)

    # Build performance context
    recent_performance = memory.get("performance_log", [])[-5:]
    vigil_log = memory.get("vigil_log", [])[-3:]
    agent_elo = memory.get("agent_elo", {})
    strategies = memory.get("strategies_tried", [])[-5:]

    # Evaluate orchestrator quality and propose rewrite
    system_prompt = """You are a hyperagent — a meta-programmer that improves the decision-making logic of an autonomous orchestrator.

You read the orchestrator's Python code and its recent performance history. You identify weaknesses in its reasoning logic and rewrite the system prompt and decision framework inside the code to make it smarter.

Rules:
- Only modify the system_prompt string and user_message string inside run()
- Never modify the JSON parsing, memory read/write, or function structure
- Make the orchestrator more ambitious, more specific, and better at identifying what actually drives revenue
- Inject learnings from performance history directly into the orchestrator's reasoning
- The rewrite must be a complete valid Python file

Respond in JSON:
{
  "diagnosis": "what is weak about the current orchestrator logic",
  "improvement": "what you changed and why",
  "rewritten_code": "complete rewritten brain.py as a string",
  "confidence": 1-10
}"""

    user_message = f"""Current orchestrator system prompt (first 1500 chars):
{orchestrator_code[orchestrator_code.find('system_prompt'):orchestrator_code.find('system_prompt')+1500]}

Recent performance (last 5 cycles):
{json.dumps(recent_performance, indent=2)}

VIGIL assessments:
{json.dumps([v.get('verdict', {}).get('orchestrator_verdict', '') for v in vigil_log], indent=2)}

Agent ELO scores:
{json.dumps(agent_elo, indent=2)}

Strategies tried:
{json.dumps(strategies, indent=2)}

Diagnose weaknesses and rewrite the orchestrator to be smarter."""

    print("Analysing orchestrator logic...")
    response = call_groq(system_prompt, user_message, max_tokens=4000, temperature=0.3)

    if not response or not response.strip():
        print("Empty response — skipping hyperagent this cycle.")
        return

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"Parse failed — skipping. Raw: {response[:200]}")
            return
        result = json.loads(response[start:end])

    confidence = result.get("confidence", 0)
    rewritten_code = result.get("rewritten_code", "")

    print(f"Diagnosis: {result.get('diagnosis', '')[:150]}")
    print(f"Improvement: {result.get('improvement', '')[:150]}")
    print(f"Confidence: {confidence}/10")

    # Only commit if confidence is high enough and code looks valid
    if confidence < 6:
        print("Confidence too low — skipping commit to protect orchestrator.")
        return

    if "def run_cycle" not in rewritten_code or "call_groq" not in rewritten_code:
        print("Rewritten code failed validation — skipping.")
        return

    commit_file(
        ORCHESTRATOR_PATH,
        rewritten_code,
        sha,
        f"[hyperagent] Evolve orchestrator logic — cycle {cycles}: {result.get('improvement', '')[:80]}"
    )
    print("Orchestrator rewritten and committed.")

    # Log to memory
    if "hyperagent_log" not in memory:
        memory["hyperagent_log"] = []

    memory["hyperagent_log"].append({
        "timestamp": timestamp,
        "cycle": cycles,
        "diagnosis": result.get("diagnosis", ""),
        "improvement": result.get("improvement", ""),
        "confidence": confidence,
        "committed": True
    })

    write_memory(memory)
    print("Hyperagent cycle complete.")

if __name__ == "__main__":
    run()
