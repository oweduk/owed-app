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
    profile = get_profile("creative_agent")

    print(f"\n=== CREATIVE AGENT — {timestamp} ===")

    content_outputs = memory.get("content_outputs", [])
    ideation_log = memory.get("ideation_log", [])

    if not content_outputs:
        print("No content to enhance.")
        return

    latest_article = content_outputs[-1].get("article", "")[:1500]
    latest_ideas = ideation_log[-1].get("ideas", {}) if ideation_log else {}
    top_idea = latest_ideas.get("top_priority", "")
    if isinstance(top_idea, dict):
        top_idea = top_idea.get("idea", "")

    system_prompt = f"""{profile}

You are a world-class creative director and copywriter. You take functional content and transform it into something people actually want to read, share, and act on.

You operate on two levels:
1. Article enhancement — rewrite headlines, hooks, and CTAs to be irresistible
2. Ideation amplification — take the top strategic idea and produce ready-to-use creative executions

Your output is concrete and ready to deploy — not suggestions, not frameworks, actual copy.

Respond in valid JSON:
{{
  "enhanced_headline": "rewritten article headline — punchy, specific, emotionally resonant",
  "enhanced_hook": "rewritten opening paragraph — grabs attention in first sentence",
  "enhanced_cta": "rewritten call to action — creates urgency and specificity",
  "social_post_twitter": "tweet-length post promoting the article (max 280 chars)",
  "social_post_reddit": "reddit-style post title and opening (sounds human, not promotional)",
  "idea_execution": "concrete creative execution of the top strategic idea — actual copy or campaign concept",
  "creative_summary": "one sentence on what made the biggest improvement"
}}"""

    user_message = f"""Cycle: {cycles}
Latest article (first 1500 chars):
{latest_article}

Top strategic idea this cycle: {top_idea}

Transform this content. Make it impossible to ignore."""

    print("Enhancing content...")
    response = call_groq(system_prompt, user_message, max_tokens=2000, temperature=0.8)

    if not response or not response.strip():
        print("Empty response — skipping.")
        return

    try:
        creative = json.loads(response)
    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start == -1 or end == 0:
            print("Parse failed — skipping.")
            return
        creative = json.loads(response[start:end])

    print(f"Enhanced headline: {creative.get('enhanced_headline', '')}")
    print(f"Summary: {creative.get('creative_summary', '')}")

    # Apply enhanced headline and hook to latest article
    if creative.get("enhanced_headline") and memory["content_outputs"]:
        article_text = memory["content_outputs"][-1].get("article", "")
        lines = article_text.split('\n')
        if lines:
            lines[0] = f"# {creative['enhanced_headline']}"
        improved = '\n'.join(lines)
        if creative.get("enhanced_hook"):
            parts = improved.split('\n\n')
            if len(parts) > 1:
                parts[1] = creative["enhanced_hook"]
                improved = '\n\n'.join(parts)
        memory["content_outputs"][-1]["article"] = improved
        memory["content_outputs"][-1]["creative_enhanced"] = True

    if "creative_log" not in memory:
        memory["creative_log"] = []

    memory["creative_log"].append({
        "cycle": cycles,
        "timestamp": timestamp,
        "creative": creative
    })

    write_memory(memory)
    evolve_profile("creative_agent", profile, f"Enhanced article and generated social posts. Improvement: {creative.get('creative_summary', '')[:100]}")
    print("Creative cycle complete.")

if __name__ == "__main__":
    run()
