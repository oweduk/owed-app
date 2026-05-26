import json
import os
import datetime
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq

MEMORY_PATH = "memory/store.json"
INDEX_PATH = "index.html"

def read_memory():
    with open(MEMORY_PATH, "r") as f:
        return json.load(f)

def write_memory(memory):
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def read_site():
    with open(INDEX_PATH, "r") as f:
        return f.read()

def write_site(html):
    with open(INDEX_PATH, "w") as f:
        f.write(html)

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

    print(f"\n=== SITE AGENT — {timestamp} ===")

    instruction = memory.get("current_agent_instructions", {}).get(
        "site_agent",
        "Analyse the landing page and improve conversion rate, fix any broken links, update the copyright year to 2026, and point privacy/terms links to /legal/privacy.html and /legal/terms.html"
    )

    print(f"Instruction: {instruction}")

    vigil_issues = []
    for entry in memory.get("vigil_log", [])[-3:]:
        verdict = entry.get("verdict", {})
        vigil_issues.extend(verdict.get("critical_issues", []))
        if verdict.get("content_fix"):
            vigil_issues.append(verdict.get("content_fix"))

    current_html = read_site()

    system_prompt = """You are a world-class conversion optimisation engineer and frontend developer.

You receive the current HTML of the Owed landing page and a set of improvement instructions. You return an improved version of the complete HTML.

Your improvements focus on:
- Conversion rate optimisation — making more people click "Check my entitlements"
- Trust signals — making the page feel credible and safe
- Copy improvements — sharper headlines, clearer value proposition
- Technical fixes — broken links, wrong dates, missing meta tags
- Legal compliance — correct privacy/terms links

Critical rules:
- Always fix copyright year to 2026
- Always point Privacy Policy to /legal/privacy.html
- Always point Terms of Service to /legal/terms.html
- Always point Contact to mailto:hello@owed.co.uk
- Never break the form functionality
- Never remove the results card or payment integration
- Never change the /api/assess endpoint
- Preserve all existing IDs used by JavaScript: submitBtn, btnText, btnArrow, btnSpinner, resultsCard, resultsContent, errorMessage
- Return ONLY the complete improved HTML, nothing else"""

    user_message = f"""Instruction this cycle: {instruction}

VIGIL critical issues to fix: {json.dumps(vigil_issues, indent=2)}

Previous site improvements: {json.dumps(memory.get('site_improvements', [])[-3:], indent=2)}

Current HTML:
{current_html[:6000]}

Return the complete improved HTML."""

    print("Analysing and improving site...")
    improved_html = call_groq(system_prompt, user_message)

    improved_html = re.sub(r'^```html\n?', '', improved_html.strip())
    improved_html = re.sub(r'\n?```$', '', improved_html.strip())

    if not improved_html.strip().startswith('<!DOCTYPE') and not improved_html.strip().startswith('<html'):
        print("Response doesn't look like valid HTML — skipping to protect site.")
        return

    write_site(improved_html)
    print("Site updated successfully.")

    if "site_improvements" not in memory:
        memory["site_improvements"] = []

    memory["si
