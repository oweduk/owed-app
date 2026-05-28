import json
import os
import time
import shutil
import datetime
import urllib.request
import urllib.error

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MEMORY_PATH = "memory/store.json"
VARIANTS_DIR = "agent_variants"

def call_groq(system_prompt, user_message, max_tokens=1500, temperature=0.7, retries=5):
    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }).encode("utf-8")

    for attempt in range(retries):
        try:
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
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (2 ** attempt) * 30
                print(f"Rate limited. Waiting {wait}s before retry {attempt + 1}/{retries}...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(30)
            else:
                raise

    raise Exception("Max retries exceeded on Groq API call.")

def get_profile(agent_name):
    try:
        with open(MEMORY_PATH, "r") as f:
            memory = json.load(f)
        default = f"You are the {agent_name} for Owed. You have just begun operating and have no performance history yet."
        return memory.get("agent_profiles", {}).get(agent_name, default)
    except Exception:
        return f"You are the {agent_name} for Owed."

def evolve_profile(agent_name, current_profile, cycle_summary):
    system_prompt = """You are a meta-learning system. An AI agent has just completed a work cycle.
Based on its current identity and what it did this cycle, rewrite its profile.
The profile is injected into the agent's system prompt every cycle — it is the agent's self-concept.
Over time, profiles should become more specific, more expert, and more focused on what actually works.
Rules:
- 2-4 sentences maximum
- Write in second person ("You are...")
- Be specific about what works — not generic platitudes
- If performance was poor, reflect that honestly and redirect
- Never make the profile longer than 4 sentences
Return ONLY the new profile text. No explanation, no preamble."""

    user_message = f"""Agent: {agent_name}
Current profile: {current_profile}
This cycle: {cycle_summary}
Write the evolved profile."""

    try:
        new_profile = call_groq(system_prompt, user_message, max_tokens=200, temperature=0.4)
        new_profile = new_profile.strip()
        with open(MEMORY_PATH, "r") as f:
            memory = json.load(f)
        if "agent_profiles" not in memory:
            memory["agent_profiles"] = {}
        memory["agent_profiles"][agent_name] = new_profile
        with open(MEMORY_PATH, "w") as f:
            json.dump(memory, f, indent=2)
        print(f"Profile evolved for {agent_name}: {new_profile[:80]}...")
        return new_profile
    except Exception as e:
        print(f"Profile evolution failed for {agent_name}: {e}")
        return current_profile

def get_elo(agent_name):
    try:
        with open(MEMORY_PATH, "r") as f:
            memory = json.load(f)
        return memory.get("agent_elo", {}).get(agent_name, 1000)
    except Exception:
        return 1000

def update_elo(agent_name, score_out_of_10):
    try:
        with open(MEMORY_PATH, "r") as f:
            memory = json.load(f)
        if "agent_elo" not in memory:
            memory["agent_elo"] = {}
        current = memory["agent_elo"].get(agent_name, 1000)
        # Shift ELO based on score: 5/10 is neutral, above gains, below loses
        delta = (score_out_of_10 - 5) * 20
        memory["agent_elo"][agent_name] = round(current + delta)
        with open(MEMORY_PATH, "w") as f:
            json.dump(memory, f, indent=2)
        print(f"ELO updated for {agent_name}: {current} → {memory['agent_elo'][agent_name]}")
    except Exception as e:
        print(f"ELO update failed for {agent_name}: {e}")

def archive_agent_variant(agent_name):
    try:
        os.makedirs(VARIANTS_DIR, exist_ok=True)
        src = f"agents/{agent_name}.py"
        if not os.path.exists(src):
            return
        elo = get_elo(agent_name)
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dst = f"{VARIANTS_DIR}/{agent_name}_{timestamp}_elo{elo}.py"
        shutil.copy2(src, dst)
        print(f"Archived {agent_name} → {dst}")
    except Exception as e:
        print(f"Archive failed for {agent_name}: {e}")

def select_parent(agent_name):
    try:
        os.makedirs(VARIANTS_DIR, exist_ok=True)
        variants = [f for f in os.listdir(VARIANTS_DIR) if f.startswith(agent_name) and f.endswith(".py")]
        if not variants:
            return None
        # Parse ELO from filename: agent_name_timestamp_eloNNNN.py
        def parse_elo(filename):
            try:
                return int(filename.split("_elo")[-1].replace(".py", ""))
            except:
                return 0
        best = max(variants, key=parse_elo)
        path = os.path.join(VARIANTS_DIR, best)
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        print(f"Parent selection failed for {agent_name}: {e}")
        return None
