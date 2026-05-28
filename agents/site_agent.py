import json
import os
import datetime
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq, get_profile, evolve_profile

MEMORY_PATH = "memory/store.json"
INDEX_PATH = "index.html"

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
    profile = get_profile("site_agent")

    print(f"\n=== SITE AGENT — {timestamp} ===")

    instruction = memory.get("current_agent_instructions", {}).get(
        "site_agent",
        "Improve conversion rate, fix broken links, update copyright to 2026, point privacy/terms to /legal/privacy.html and /legal/terms.html"
    )

    vigil_issues = []
    for entry in memory.get("vigil_log", [])[-3:]:
        verdict = entry.get("verdict", {})
        vigil_issues.extend(verdict.get("critical_issues", []))

    with open(INDEX_PATH, "r") as f:
        current_html = f.read()

    system_prompt = f"""{profile}

Critical rules — never violate these:
- Fix copyright year to 2026
- Point Privacy Policy to /legal/privacy.html
- Point Terms of Service to /legal/terms.html
- Point Contact to mailto:hello@owed.co.uk
- Never break form functionality
- Never remove results card or payment integration
- Never change the /api/assess endpoint
- Preserve all JS IDs: submitBtn, btnText, btnArrow, btnSpinner, resultsCard, resultsContent, errorMessage
- Return ONLY the complete improved HTML — no explanation, no markdown fences"""

    user_message = f"""Instruction: {instruction}
VIGIL issues: {json.dumps(vigil_issues, indent=2)}
Previous improvements: {json.dumps(memory.get('site_improvements', [])[-2:], indent=2)}
Current HTML (first 3000 chars): {current_html[:3000]}

Return complete improved HTML."""

    print("Improving site...")
    improved_html = call_groq(system_prompt, user_message, max_tokens=4000, temperature=0.4)

    improved_html = re.sub(r'^```html\n?', '', improved_html.strip())
    improved_html = re.sub(r'\n?```$', '', improved_html.strip())

    if not improved_html.strip().startswith('<!DOCTYPE') and not improved_html.strip().startswith('<html'):
        print("Response not valid HTML — skipping to protect site.")
        return

    # Safety check — only write if significantly different but not drastically shorter
    if len(improved_html) < len(current_html) * 0.8:
        print("Improved HTML is significantly shorter than original — skipping to protect site.")
        return

    with open(INDEX_PATH, "w") as f:
        f.write(improved_html)
    print("Site updated.")

    memory.setdefault("site_improvements", []).append({
        "cycle": cycles, "timestamp": timestamp, "instruction": instruction
    })
    write_memory(memory)

    evolve_profile("site_agent", profile, f"Updated index.html. Instruction: {instruction[:100]}")
    print("Site agent cycle complete.")

if __name__ == "__main__":
    run()
