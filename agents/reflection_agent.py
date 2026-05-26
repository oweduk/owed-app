import json
import os
import datetime
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

def run():
    memory = read_memory()
    timestamp = datetime.datetime.utcnow().isoformat()
    cycles = memory.get("cycles", 0)

    print(f"\n=== REFLECTION AGENT (VIGIL) — {timestamp} ===")

    system_prompt = """You are VIGIL — a brutally honest reflection daemon for the Owed autonomous system.

Your job is to watch everything the system produces and be merciless about quality and effectiveness.

You evaluate:
1. Content quality — are the articles genuinely useful, well-written, and SEO-optimised? Or generic and weak?
2. Orchestrator decisions — are the strategies actually ambitious and specific? Or vague and safe?
3. System health — are there signs of degradation, repetition, or drift from the goal?
4. Agent instruction quality — are the instructions specific enough to produce great output?

You are not here to be nice. You are here to make the system better.

You respond in valid JSON with this exact structure:
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

    user_message = f"""Current cycle: {cycles}
Goal: {memory.get('goal', '')}

Recent orchestrator decisions:
{json.dumps(recent_cycles, indent=2)}

Current agent instructions:
{json.dumps(current_instructions, indent=2)}

Recent content produced:
{json.dumps([{"instruction": a.get("instruction"), "preview": a.get("article", "")[:400]} for a in recent_articles], indent=2)}

Strategies tried so far:
{json.dumps(memory.get('strategies_tried', []), indent=2)}

Evaluate everything brutally. Identify what is weak and rewrite the instructions to be better."""

    print("Analysing system health...")
    response = call_groq(system_prompt, user_message)

    try:
        verdict = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        verdict = json.loads(response[start:end])

    print(f"\nSystem health: {verdict.get('overall_health', 'unknown')}")
    print(f"Content quality: {verdict.get('content_quality_score', '?')}/10 — {verdict.get('content_verdict', '')}")
    print(f"Orchestrator quality: {verdict.get('orchestrator_quality_score', '?')}/10 — {verdict.get('orchestrator_verdict', '')}")
    print(f"VIGIL verdict: {verdict.get('vigil_summary', '')}")

    if "vigil_log" not in memory:
        memory["vigil_log"] = []

    memory["vigil_log"].append({
        "cycle": cycles,
        "timestamp": timestamp,
        "verdict": verdict
    })

    if verdict.get("rewritten_content_instruction"):
        if "current_agent_instructions" not in memory:
            memory["current_agent_instructions"] = {}
        memory["current_agent_instructions"]["content_agent"] = verdict["rewritten_content_instruction"]
        print("\nContent agent instruction rewritten by VIGIL.")

    if verdict.get("rewritten_orchestrator_goal"):
        memory["goal"] = verdict["rewritten_orchestrator_goal"]
        print("Orchestrator goal updated by VIGIL.")

    critical = verdict.get("critical_issues", [])
    if critical:
        print(f"\nCritical issues flagged: {critical}")

    write_memory(memory)
    print("\nVIGIL cycle complete. Memory updated.")

if __name__ == "__main__":
    run()
