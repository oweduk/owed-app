import json
import os
import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq, get_profile, evolve_profile

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
    profile = get_profile("ideation_agent")

    print(f"\n=== IDEATION AGENT — {timestamp} ===")

    system_prompt = f"""{profile}

You are a relentlessly ambitious ideation engine for Owed — a UK benefits checker at owed-app.vercel.app earning 10% success fees.

Every cycle you generate provocative, specific, actionable ideas across five categories:
1. Growth — how to get more users
2. Monetisation — new or improved revenue streams
3. Product — features that increase conversion or retention
4. Content — angles, formats, or topics that will dominate search or go viral
5. Partnerships — organisations, tools, or platforms to collaborate with

You are not conservative. You propose things that seem ambitious. You think about what would make this the dominant UK benefits tool within 12 months.

Respond in valid JSON:
{{
  "growth": [{{"idea": "specific idea", "impact": "high/medium/low", "effort": "high/medium/low"}}],
  "monetisation": [{{"idea": "specific idea", "impact": "high/medium/low", "effort": "high/medium/low"}}],
  "product": [{{"idea": "specific idea", "impact": "high/medium/low", "effort": "high/medium/low"}}],
  "content": [{{"idea": "specific idea", "impact": "high/medium/low", "effort": "high/medium/low"}}],
  "partnerships": [{{"idea": "specific idea", "impact": "high/medium/low", "effort": "high/medium/low"}}],
  "top_priority": "the single highest impact idea across all categories this cycle",
  "ideation_summary": "one sentence on the strategic theme this cycle"
}}"""

    recent_performance = memory.get("performance_log", [])[-3:]
    strategies_tried = memory.get("strategies_tried", [])[-5:]
    previous_ideas = [e.get("top_priority", "") for e in memory.get("ideation_log", [])[-5:]]

    user_message = f"""Cycle: {cycles}
Goal: {memory.get('goal', '')}
Recent performance: {json.dumps(recent_performance, indent=2)}
Strategies already tried: {json.dumps(strategies_tried, indent=2)}
Previous top ideas: {json.dumps(previous_ideas, indent=2)}

Generate fresh ideas. Don't repeat previous suggestions. Be ambitious."""

    print("Generating ideas...")
    response = call_groq(system_prompt, user_message, max_tokens=2000, temperature=0.9)

    if not response or not response.strip():
        print("Empty response — skipping.")
        return

    try:
        ideas = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"Parse failed — skipping.")
            return
        ideas = json.loads(response[start:end])

    print(f"Top priority: {ideas.get('top_priority', '')}")
    print(f"Theme: {ideas.get('ideation_summary', '')}")

    total = sum(len(ideas.get(k, [])) for k in ["growth", "monetisation", "product", "content", "partnerships"])
    print(f"Ideas generated: {total}")

    if "ideation_log" not in memory:
        memory["ideation_log"] = []

    memory["ideation_log"].append({
        "cycle": cycles,
        "timestamp": timestamp,
        "ideas": ideas
    })

    # Feed top priority into orchestrator context
    memory.setdefault("current_agent_instructions", {})["ideation_top_priority"] = ideas.get("top_priority", "")

    write_memory(memory)
    evolve_profile("ideation_agent", profile, f"Generated {total} ideas. Top priority: {ideas.get('top_priority', '')[:100]}")
    print("Ideation cycle complete.")

if __name__ == "__main__":
    run()
