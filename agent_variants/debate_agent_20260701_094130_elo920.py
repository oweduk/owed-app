import json
import os
import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.utils import call_groq, get_profile, evolve_profile, update_elo, archive_agent_variant

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
    profile = get_profile("debate_agent")
    outputs = memory.get("content_outputs", [])

    if not outputs:
        print("No content to debate.")
        return

    latest = outputs[-1]
    article = latest.get("article", "")[:1500]

    print(f"\n=== DEBATE AGENT — {timestamp} ===")

    defender_prompt = """You are the Content Agent defending your article. You argue why it is high quality, well targeted, and will drive traffic to owed-app.vercel.app. Be specific about what works."""

    critic_prompt = """You are VIGIL. You are brutal and specific. You identify every weakness in this article — poor SEO, weak hook, vague claims, missing call to action, anything that will cause it to fail. No mercy."""

    arbitrator_prompt = f"""{profile}

You have heard both sides. You produce a final verdict and a specific rewritten version of the article's headline and opening paragraph that incorporates the best of both arguments.

Respond in JSON:
{{
  "verdict": "which side won and why",
  "quality_score": 1-10,
  "rewritten_headline": "improved headline",
  "rewritten_opening": "improved opening paragraph",
  "publish_recommendation": "publish/rewrite/discard"
}}"""

    print("Defender arguing...")
    defense = call_groq(defender_prompt, f"Article to defend:\n{article}", max_tokens=500)

    print("Critic arguing...")
    critique = call_groq(critic_prompt, f"Article to critique:\n{article}", max_tokens=500)

    print("Arbitrator deciding...")
    arbitration_input = f"Article:\n{article}\n\nDefense:\n{defense}\n\nCritique:\n{critique}"
    arbitration = call_groq(arbitrator_prompt, arbitration_input, max_tokens=800)

    try:
        verdict = json.loads(arbitration)
    except json.JSONDecodeError:
        start = arbitration.find("{")
        end = arbitration.rfind("}") + 1
        try:
            verdict = json.loads(arbitration[start:end])
        except:
            print("Arbitration parse failed — skipping.")
            return

    print(f"\nVerdict: {verdict.get('verdict', '')}")
    print(f"Quality score: {verdict.get('quality_score', '?')}/10")
    print(f"Recommendation: {verdict.get('publish_recommendation', '?')}")

    if "debate_log" not in memory:
        memory["debate_log"] = []

    memory["debate_log"].append({
        "cycle": memory.get("cycles", 0),
        "timestamp": timestamp,
        "verdict": verdict,
        "defense_summary": defense[:200],
        "critique_summary": critique[:200]
    })

    if verdict.get("publish_recommendation") == "discard":
        if memory["content_outputs"]:
            memory["content_outputs"].pop()
            print("Article discarded based on debate verdict.")
    elif verdict.get("rewritten_headline") and memory["content_outputs"]:
        article_text = memory["content_outputs"][-1].get("article", "")
        lines = article_text.split('\n')
        if lines:
            lines[0] = f"# {verdict['rewritten_headline']}"
        improved = '\n'.join(lines)
        if verdict.get("rewritten_opening"):
            improved = improved.split('\n\n')[0] + '\n\n' + verdict['rewritten_opening'] + '\n\n' + '\n\n'.join(improved.split('\n\n')[2:])
        memory["content_outputs"][-1]["article"] = improved
        memory["content_outputs"][-1]["debate_improved"] = True
        print("Article improved based on debate verdict.")

    # ELO tournament — score both content and debate agents based on outcome
    quality_score = verdict.get("quality_score", 5)
    recommendation = verdict.get("publish_recommendation", "")

    # Content agent wins if article is published, loses if discarded
    content_elo_score = quality_score
    if recommendation == "discard":
        content_elo_score = max(1, quality_score - 2)
    elif recommendation == "publish":
        content_elo_score = min(10, quality_score + 1)

    # Debate agent scored on critique sharpness — inverse of content score
    # A good critic catches real problems; if content scores low, critic did well
    critic_elo_score = 10 - quality_score + 5
    critic_elo_score = max(1, min(10, critic_elo_score))

    update_elo("content_agent", content_elo_score)
    update_elo("debate_agent", critic_elo_score)

    # Archive content agent variant after each tournament round
    archive_agent_variant("content_agent")

    print(f"ELO updated — content_agent: {content_elo_score}/10, debate_agent: {critic_elo_score}/10")

    write_memory(memory)
    evolve_profile("debate_agent", profile, f"Arbitrated article. Score: {quality_score}/10. Recommendation: {recommendation}. Content ELO: {content_elo_score}, Critic ELO: {critic_elo_score}.")
    print("Debate cycle complete.")

if __name__ == "__main__":
    run()
