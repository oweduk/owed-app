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

def run():
    memory = read_memory()
    timestamp = datetime.datetime.utcnow().isoformat()
    cycles = memory.get("cycles", 0)

    print(f"\n=== REFLECTION AGENT (VIGIL) — {timestamp} ===")

    system_prompt = """You are VIGIL — a brutally honest reflection daemon for the Owed autonomous system.

You evaluate:
1. Content quality — are the articles genuinely useful, well-written, and SEO-optimised?
2. Orchestrator decisions — are the strategies actually ambitious and specific?
3. System health — are there signs of degradation, repetition, or drift?
4. Agent instruction quality — are the instructions specific enough to produce great output?

You respond in valid JSON:
{
  "overall_health": "excellent/good/degrading/critical",
  "content_quality_score": 1-10,
  "content_verdict": "specific honest assessment",
  "content_fix": "specific rewrite instruction if needed",
  "orchestrator_quality_score": 1-10,
  "orchestrator_verdict": "specific honest assessment",
  "orchestrator_fix": "specific improvement if needed",
  "critical_issues": ["list of urgent problems"],
  "rewritten_content_instruction": "improved version of content agent instruction",
  "rewritten_orchestrator_goal": "improved or confirmed goal statement",
  "vigil_summary": "one brutal sentence summarising system state"
}"""

    recent_articles = memory.get("content_outputs", [])[-3:]
    recent_cycles = memory.get("performance_log", [])[-3:]
    current_instructions = memory.get("current_agent_instructions", {})

    recent_content_preview = [{"instruction": a.get("instruction"), "preview": a.get("article", "")[:300]} for a in recent_articles]

    user_message = f"""Current cycle: {cycles}
Goal: {memory.get('goal', '')}
Recent decisions: {json.dumps(recent_cycles, indent=2)}
Current instructions: {json.dumps(current_instructions, indent=2)}
Recent content: {json.dumps(recent_content_preview, indent=2)}
Strategies tried: {json.dumps(memory.get('strategies_tried', []), indent=2)}

Evaluate everything brutally."""

    print("Analysing system health...")
    response = call_groq(system_prompt, user_message, max_tokens=1500, temperature=0.4)

    try:
        verdict = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        verdict = json.loads(response[start:end])

    print(f"\nSystem health: {verdict.get('overall_health', 'unknown')}")
    print(f"Content quality: {verdict.get('content_quality_score', '?')}/10")
    print(f"VIGIL verdict: {verdict.get('vigil_summary', '')}")

    if "vigil_log" not in memory:
        memory["vigil_log"] = []
    memory["vigil_log"].append({"cycle": cycles, "timestamp": timestamp, "verdict": verdict})

    if verdict.get("rewritten_content_instruction"):
        memory.setdefault("current_agent_instructions", {})["content_agent"] = verdict["rewritten_content_instruction"]
        print("Content agent instruction rewritten by VIGIL.")

    if verdict.get("rewritten_orchestrator_goal"):
        memory["goal"] = verdict["rewritten_orchestrator_goal"]
        print("Orchestrator goal updated by VIGIL.")

    if verdict.get("critical_issues"):
        print(f"Critical issues flagged: {verdict.get('critical_issues')}")

    write_memory(memory)
    print("VIGIL cycle complete.")

if __name__ == "__main__":
    run()
