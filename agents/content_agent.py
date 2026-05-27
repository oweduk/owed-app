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
    instruction = memory.get("current_agent_instructions", {}).get("content_agent", "Write an SEO article about UK benefits entitlement.")
    timestamp = datetime.datetime.utcnow().isoformat()

    print(f"\n=== CONTENT AGENT — {timestamp} ===")
    print(f"Instruction: {instruction}")

    system_prompt = """You are a world-class SEO content writer specialising in UK benefits and welfare.
You write articles that rank on Google and genuinely help people find money they are owed by the government.

Every article you write:
- Targets a specific high-volume UK search query
- Has a compelling headline
- Is 600-800 words
- Is written in plain English, warm and direct
- Includes a clear call to action directing readers to owed-app.vercel.app
- Is formatted in clean markdown

You respond with ONLY the article in markdown. No preamble, no explanation."""

    user_message = f"""Your instruction this cycle: {instruction}

Write one complete SEO article now. Make it genuinely useful and compelling."""

    print("Writing article...")
    article = call_groq(system_prompt, user_message, max_tokens=1500)

    if "content_outputs" not in memory:
        memory["content_outputs"] = []

    memory["content_outputs"].append({
        "timestamp": timestamp,
        "instruction": instruction,
        "article": article,
        "cycle": memory.get("cycles", 0)
    })

    write_memory(memory)
    print("Article written and saved to memory.")

if __name__ == "__main__":
    run()
