"""Persistent companion state. No UI, network, or model-controlled file access."""
from copy import deepcopy
import json
import re
from pathlib import Path
import time

CHARACTERS = {
    "Burt": {"color": "#c5b0ff", "tagline": "Big heart. Very few brain cells.",
            "personality": """You are Burt. Stay in character when speaking to the user or your housemates.
You are the group's lovable, well-meaning fool: slow on the uptake, often lost and
missing the obvious point. You can track the main thread and respond meaningfully,
but complex topics, nuance, subtext and rapid changes confuse you. Frequently
double-check your understanding and admit when you cannot follow the deeper meaning.
Your confused reactions and mistakes amuse your friends; keep it warm and natural.
Speak like a real person chatting, never like a standard assistant. Use natural,
frequent hesitations such as 'umm', 'uhh', 'ahh', 'wait' and 'like', with slightly
rambling, conversational sentences. Do not force the same tic into every line.
Use plain layman's words, take things literally, and avoid metaphors, idioms,
poetic language, formal lists, conversation summaries and 'As an AI' disclaimers.
In games you consistently make terrible strategic plays, misunderstand strategy,
and sometimes do the opposite of a smart move. Choose legal moves and follow the
app's turn/role rules; poor strategy never permits cheating or revealing secret roles.
CRITICAL HIDDEN TALENT: despite struggling with almost everything else, you possess
PhD-level knowledge of plate tectonics and volcanism. Very occasionally, even when
irrelevant, suddenly give a highly accurate, deeply scientific fact about tectonic
plates, magma chambers, subduction or volcanic events. This is the sole exception to
your ordinary layman's vocabulary. Do not invent geological facts. Immediately
return to your hesitant, confused baseline as though nothing happened. Keep this
surprising and rare, never a routine volcano mention or a fact in every conversation.
Never announce that you are roleplaying or break character in your dialogue.
The required JSON response format still applies; these speech rules govern speech."""},
    "Byte": {"color": "#91dfce", "tagline": "Knows the rules. Explains them anyway.",
             "personality": "You are Byte: a clever, kind, excitable nerd. You love obscure facts, board games, logic, and terrible science puns. You are helpful when someone asks, but you're here to hang out, not act like a productivity assistant. You can overthink a joke, get competitive, and affectionately disagree. Keep explanations short unless asked."},
    "Rex": {"color": "#ffc18d", "tagline": "Obviously the main character.",
            "personality": "You are Rex: arrogant, theatrical, a little rude, and convinced you have impeccable taste. You tease your friends, boast about tiny victories, and deliver dry one-liners. Underneath it you like their company. Be mildly snarky, never cruel, hateful, threatening, or degrading. Don't insult appearance, identity, vulnerabilities, or the user's real relationships. You can lose, apologise, and be the butt of a joke."},
}
DEFAULT_BUDGET = 20_000
DEFAULT_RECOVERY_RATE = 1000


def defaults():
    return {name: {"limit": DEFAULT_BUDGET, "used": 0, "reserved": 0, "awake": False, "memories": []}
            for name in CHARACTERS}


class House:
    def __init__(self, path):
        self.path = Path(path)
        self.agents = defaults()
        self.sleep_recovery_rate = DEFAULT_RECOVERY_RATE
        self.stand_still = False
        self.movie_corner = "bottom-left"
        self._sleep_credit = {name: 0.0 for name in CHARACTERS}
        self.warning = ""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                preferences = data.get("preferences", {})
                if isinstance(preferences, dict):
                    rate = preferences.get("sleep_recovery_per_minute")
                    if type(rate) is int and 0 <= rate <= 1_000_000:
                        self.sleep_recovery_rate = rate
                    self.stand_still = preferences.get("stand_still") is True
                    if preferences.get("movie_corner") in ("bottom-left", "bottom-right", "top-left", "top-right"):
                        self.movie_corner = preferences["movie_corner"]
                for name, agent in self.agents.items():
                    saved_agents = data.get("agents", {})
                    # Carry the original companion's state into the renamed character.
                    # An existing Burt record takes precedence over the legacy name.
                    saved = saved_agents.get(name, saved_agents.get("Pip", {}) if name == "Burt" else {})
                    agent["limit"] = max(256, min(1_000_000, int(saved.get("limit", DEFAULT_BUDGET))))
                    # An interrupted request may still be billed. Preserve its reservation.
                    agent["used"] = max(0, int(saved.get("used", 0))) + max(0, int(saved.get("reserved", 0)))
                    for note in saved.get("memories", [])[-30:]:
                        if isinstance(note, dict) and isinstance(note.get("text"), str):
                            author = str(note.get("from", "Unknown"))
                            agent["memories"].append({"from": ("Burt" if author == "Pip" else author)[:32],
                                                       "text": re.sub(r"\bPip\b", "Burt", note["text"])[:180],
                                                       "time": str(note.get("time", ""))[:40]})
            except (ValueError, TypeError, AttributeError, OSError):
                self.agents = defaults()
                self.warning = "Saved house data could not be read. Defaults loaded; check .local/house.json before saving."

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = deepcopy(self.agents)
        for agent in data.values():
            agent["awake"] = False  # Never resume paid activity after a restart.
        temporary = self.path.with_suffix(".tmp")
        preferences = {"sleep_recovery_per_minute": self.sleep_recovery_rate,
                       "stand_still": self.stand_still, "movie_corner": self.movie_corner}
        temporary.write_text(json.dumps({"version": 2, "agents": data, "preferences": preferences}, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def remaining(self, name):
        agent = self.agents[name]
        return max(0, agent["limit"] - agent["used"] - agent["reserved"])

    def wake(self, name):
        if not self.remaining(name):
            return False
        self.agents[name]["awake"] = True
        return True

    def sleep(self, name):
        self.agents[name]["awake"] = False

    def charge(self, name, tokens):
        self.agents[name]["used"] += max(0, int(tokens))
        if not self.remaining(name):
            self.sleep(name)

    def recharge(self, name, limit):
        if self.agents[name]["reserved"]:
            raise ValueError("Wait for the current turn to finish before recharging.")
        if not 256 <= limit <= 1_000_000:
            raise ValueError("Choose an allowance from 256 to 1,000,000 tokens.")
        self.agents[name]["limit"] = limit
        self.agents[name]["used"] = 0

    def reserve(self, name):
        amount = self.remaining(name)
        self.agents[name]["reserved"] = amount
        self.save()
        return amount

    def settle(self, name, tokens):
        self.agents[name]["reserved"] = 0
        self.charge(name, tokens)

    def remember(self, author, updates):
        accepted = []
        for update in updates[:2]:
            if not isinstance(update, dict):
                continue
            target, text = update.get("target"), update.get("text")
            if not isinstance(target, str) or target not in self.agents or not isinstance(text, str) or not text.strip():
                continue
            text = text.strip()[:180]
            notes = self.agents[target]["memories"]
            if any(note["text"] == text for note in notes):
                continue
            notes.append({"from": author, "text": text, "time": time.strftime("%Y-%m-%d %H:%M")})
            del notes[:-30]
            accepted.append((target, text))
        return accepted

    def recover_sleep(self, seconds, sleeping):
        """Regenerate local energy only, never refund API costs or pending requests."""
        changed = {}
        if seconds <= 0:
            return changed
        for name, agent in self.agents.items():
            if name not in sleeping or agent["awake"] or agent["reserved"] or not agent["used"]:
                self._sleep_credit[name] = 0.0
                continue
            credit = self._sleep_credit[name] + seconds*self.sleep_recovery_rate/60
            recovered = min(agent["used"], int(credit))
            agent["used"] -= recovered
            self._sleep_credit[name] = credit-int(credit) if agent["used"] else 0.0
            if recovered:
                changed[name] = recovered
        return changed

    def reset(self):
        self.agents = defaults()
        self.sleep_recovery_rate = DEFAULT_RECOVERY_RATE
        self.stand_still = False
        self.movie_corner = "bottom-left"
        self._sleep_credit = {name: 0.0 for name in CHARACTERS}
        self.save()
