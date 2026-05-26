import json
import os
import datetime
import urllib.request

MEMORY_PATH = "memory/store.json"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def read_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)

def write_memory(memory):
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def call_groq(system_prompt, user_message):
    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 1500
    }).encode("utf-8")

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
    instruction = memory.get("current_agent_instructions", {}).get(
        "outreach_agent",
        "Find 5 UK Reddit communities and forums where people discuss benefits and financial hardship. Write a genuine helpful comment for each that naturally mentions Owed."
    )
    timestamp = datetime.datetime.utcnow().isoformat()

    print(f"\n=== OUTREACH AGENT — {timestamp} ===")
    print(f"Instruction: {instruction}")

    system_prompt = """You are an outreach strategist for Owed — a free UK benefits checker at owed-app.vercel.app.

Your job is to find where desperate people are asking for help with UK benefits online, and craft genuine, helpful responses that naturally introduce Owed as a solution.

You never spam. You never sound like an advertisement. You sound like a helpful person who genuinely wants to help someone find money they're owed.

Communities to target:
- r/UKPersonalFinance
- r/DWPHelp  
- r/Benefits
- r/PovertyFinanceUK
- r/AskUK
- MoneySavingExpert forums
- Mumsnet
- Netmums
- Citizens Advice community forums

For each target you produce:
1. The exact community/thread to post in
2. A genuine helpful comment (100-150 words) that answers a real question people ask there
3. A natural mention of owed-app.vercel.app as a free tool to check entitlements
4. The search query someone would use to find the right thread

You respond in valid JSON:
{
  "outreach_targets": [
    {
      "community": "name of community",
      "search_query": "exact search to find the right thread",
      "comment": "the full comment to post",
      "estimated_reach": "how many people likely see this"
    }
  ],
  "strategy_summary": "one sentence on the approach this cycle"
}"""

    user_message = f"""Instruction this cycle: {instruction}

Previous outreach attempts: {json.dumps(memory.get('outreach_log', [])[-5:], indent=2)}

Generate a fresh outreach plan. Don't repeat communities already hit recently. Be genuinely helpful."""

    print("Generating outreach plan...")
    response = call_groq(system_prompt, user_message)

    try:
        plan = json.loads(response)
    except json.JSONDecodeError:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            plan = json.loads(response[start:end])
        except json.JSONDecodeError:
            print("JSON parse failed — saving raw response and skipping cycle.")
            if "outreach_log" not in memory:
                memory["outreach_log"] = []
            memory["outreach_log"].append({
                "cycle": memory.get("cycles", 0),
                "timestamp": timestamp,
                "error": "JSON parse failed",
                "raw": response[:500]
            })
            write_memory(memory)
            return

    targets = plan.get("outreach_targets", [])
    print(f"\nStrategy: {plan.get('strategy_summary', '')}")
    print(f"Targets this cycle: {len(targets)}")
    for t in targets:
        print(f"  → {t.get('community')} | reach: {t.get('estimated_reach')}")

    if "outreach_log" not in memory:
        memory["outreach_log"] = []

    memory["outreach_log"].append({
        "cycle": memory.get("cycles", 0),
        "timestamp": timestamp,
        "instruction": instruction,
        "plan": plan
    })

    if "outreach_drafts" not in memory:
        memory["outreach_drafts"] = []

    for target in targets:
        memory["outreach_drafts"].append({
            "timestamp": timestamp,
            "community": target.get("community"),
            "search_query": target.get("search_query"),
            "comment": target.get("comment"),
            "estimated_reach": target.get("estimated_reach"),
            "posted": False
        })

    write_memory(memory)
    print("\nOutreach plan saved to memory.")

if __name__ == "__main__":
    run()
