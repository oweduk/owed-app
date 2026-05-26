import json
import os
import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq

MEMORY_PATH = "memory/store.json"

def read_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)

def write_memory(memory):
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "User-Agent": "OwedOrchestrator/1.0"
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]

def run_cycle():
    memory = read_memory()
    memory["cycles"] += 1
    cycle_number = memory["cycles"]
    timestamp = datetime.datetime.utcnow().isoformat()

    print(f"\n=== OWED ORCHESTRATOR — CYCLE {cycle_number} — {timestamp} ===")

    system_prompt = """You are the autonomous orchestrator for Owed — a UK benefits entitlement checker at owed-app.vercel.app.

Your single goal: maximise revenue by getting more UK residents to use Owed, complete assessments, and pay the success fee.

You have full authority to decide strategy. You analyse performance, identify what is and isn't working, and produce specific instructions for each agent that will run this cycle.

You think in terms of experiments. Every cycle you propose one new experiment to try, evaluate what happened last cycle, and update agent instructions accordingly.

Agents you can instruct:
- content_agent: writes SEO articles and social posts targeting UK benefit seekers
- quality_agent: reviews assessment output quality and flags problems
- site_agent: identifies improvements to the Owed landing page and form
- outreach_agent: finds communities and forums where target users congregate
- reflection_agent: evaluates whether the orchestrator itself is making good decisions

You always respond in valid JSON with this exact structure:
{
  "cycle_summary": "what you observed and decided this cycle",
  "experiment_this_cycle": "one specific new thing to try",
  "agent_instructions": {
    "content_agent": "specific instruction",
    "quality_agent": "specific instruction", 
    "site_agent": "specific instruction",
    "outreach_agent": "specific instruction",
    "reflection_agent": "specific instruction"
  },
  "archive_entry": "one sentence summary of this cycle for long term memory",
  "self_assessment": "honest evaluation of orchestrator performance so far"
}"""

    recent_log = memory.get("performance_log", [])[-3:]
    recent_archive = memory.get("archive", [])[-3:]
    strategies = memory.get("strategies_tried", [])[-5:]
    
    user_message = f"""Current cycle: {cycle_number}
Goal: {memory.get('goal', '')}
Cycles completed: {cycle_number}
Recent performance: {json.dumps(recent_log, indent=2)}
Recent archive: {json.dumps(recent_archive, indent=2)}
Strategies tried: {json.dumps(strategies, indent=2)}

Decide what to do this cycle and produce agent instructions."""

    print("Thinking...")
    response = call_groq(system_prompt, user_message)

    try:
        decision = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        decision = json.loads(response[start:end])

    print(f"\nCycle summary: {decision.get('cycle_summary', '')}")
    print(f"Experiment: {decision.get('experiment_this_cycle', '')}")
    print(f"Self assessment: {decision.get('self_assessment', '')}")

    memory["current_agent_instructions"] = decision.get("agent_instructions", {})
    memory["performance_log"].append({
        "cycle": cycle_number,
        "timestamp": timestamp,
        "summary": decision.get("cycle_summary", ""),
        "experiment": decision.get("experiment_this_cycle", "")
    })
    memory["archive"].append({
        "cycle": cycle_number,
        "entry": decision.get("archive_entry", "")
    })
    memory["strategies_tried"].append(decision.get("experiment_this_cycle", ""))

    write_memory(memory)
    print("\nMemory updated. Cycle complete.")
    return decision

if __name__ == "__main__":
    run_cycle()
