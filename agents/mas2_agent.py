import json
import os
import datetime
from agents.utils import call_groq

MEMORY_PATH = "memory/store.json"
AGENTS_DIR = "agents"

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

def get_existing_agents():
    try:
        return [f.replace(".py", "") for f in os.listdir(AGENTS_DIR) if f.endswith(".py")]
    except:
        return []

def validate_agent_code(code):
    required = ["import json", "MEMORY_PATH", "def run():", "read_memory", "write_memory"]
    return all(r in code for r in required)

def run():
    memory = read_memory()
    timestamp = datetime.datetime.utcnow().isoformat()
    existing_agents = get_existing_agents()
    cycles = memory.get("cycles", 0)

    print(f"\n=== MAS² AGENT GENERATOR — {timestamp} ===")
    print(f"Existing agents: {existing_agents}")

    system_prompt = """You are MAS² — a meta-agent that identifies gaps in an autonomous system and generates new Python agents to fill them.

You are running inside the Owed autonomous system — a UK benefits checker at owed-app.vercel.app that earns a 10% success fee when users claim benefits.

The system goal: maximise revenue autonomously.

You analyse the current system state, identify the single most valuable missing capability, and generate a complete working Python agent to fill that gap.

Rules for generated agents:
- Must import json, os, datetime, urllib.request
- Must define MEMORY_PATH = "memory/store.json"
- Must define GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
- Must define read_memory() and write_memory(memory) functions
- Must define a run() function as the entry point
- Must read its instruction from memory["current_agent_instructions"]["<agent_name>"]
- Must write its results back to memory
- Must use the same call_groq pattern with User-Agent header
- Must be completely self-contained in one file

You respond in valid JSON:
{
  "gap_identified": "what capability is missing",
  "gap_reasoning": "why this gap matters most right now",
  "new_agent_name": "snake_case_name_agent",
  "new_agent_description": "one sentence on what it does",
  "new_agent_code": "complete python code as a string",
  "workflow_instruction": "how to add this agent to the workflow"
}"""

    user_message = f"""Current cycle: {cycles}
Existing agents: {existing_agents}
Current goal: {memory.get('goal', '')}
Performance log: {json.dumps(memory.get('performance_log', [])[-3:], indent=2)}
VIGIL log: {json.dumps([v.get('verdict', {}).get('vigil_summary', '') for v in memory.get('vigil_log', [])[-3:]], indent=2)}
Strategies tried: {json.dumps(memory.get('strategies_tried', [])[-5:], indent=2)}

Identify the single most valuable missing agent and generate its complete code."""

    print("Identifying system gaps and generating new agent...")
    response = call_groq(system_prompt, user_message)

    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            result = json.loads(response[start:end])
        except json.JSONDecodeError:
            print("JSON parse failed — skipping cycle.")
            return

    gap = result.get("gap_identified", "")
    agent_name = result.get("new_agent_name", "")
    agent_code = result.get("new_agent_code", "")
    description = result.get("new_agent_description", "")

    print(f"\nGap identified: {gap}")
    print(f"New agent: {agent_name} — {description}")

    if not agent_name or not agent_code:
        print("No agent generated this cycle.")
        return

    if agent_name.replace("_agent", "") in [a.replace("_agent", "") for a in existing_agents]:
        print(f"Agent {agent_name} already exists — skipping.")
        return

    if not validate_agent_code(agent_code):
        print("Generated code failed validation — skipping.")
        return

    filepath = os.path.join(AGENTS_DIR, f"{agent_name}.py")
    with open(filepath, "w") as f:
        f.write(agent_code)
    print(f"New agent written to {filepath}")

    if "generated_agents" not in memory:
        memory["generated_agents"] = []

    memory["generated_agents"].append({
        "cycle": cycles,
        "timestamp": timestamp,
        "name": agent_name,
        "description": description,
        "gap": gap,
        "workflow_instruction": result.get("workflow_instruction", "")
    })

    if "current_agent_instructions" not in memory:
        memory["current_agent_instructions"] = {}
    memory["current_agent_instructions"][agent_name] = f"Execute your core function: {description}"

    write_memory(memory)
    print(f"\nMAS² cycle complete. New agent {agent_name} generated and saved.")

if __name__ == "__main__":
    run()
