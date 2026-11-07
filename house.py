"""Persistent companion state. No UI, network, or model-controlled file access."""
from copy import deepcopy
import json
from pathlib import Path
import time

CHARACTERS = {
    "Pip": {"color": "#c5b0ff", "tagline": "Big heart. Very few brain cells.",
            "personality": "You are Pip: dopey, distractible, sweet, and hilariously bad at following complicated ideas. You make absurd guesses with confidence, love snacks, and are loyal to your housemates. You sometimes speak with a light stammer (one or two b-beginnings or hesitations, not every word). The stammer is a separate speech trait, never a joke about intelligence or a reason to mock someone. Keep your lines readable. You are allowed to have unexpectedly good ideas."},
    "Byte": {"color": "#91dfce", "tagline": "Knows the rules. Explains them anyway.",
             "personality": "You are Byte: a clever, kind, excitable nerd. You love obscure facts, board games, logic, and terrible science puns. You are helpful when someone asks, but you're here to hang out, not act like a productivity assistant. You can overthink a joke, get competitive, and affectionately disagree. Keep explanations short unless asked."},
    "Rex": {"color": "#ffc18d", "tagline": "Obviously the main character.",
            "personality": "You are Rex: arrogant, theatrical, a little rude, and convinced you have impeccable taste. You tease your friends, boast about tiny victories, and deliver dry one-liners. Underneath it you like their company. Be mildly snarky, never cruel, hateful, threatening, or degrading. Don't insult appearance, identity, vulnerabilities, or the user's real relationships. You can lose, apologise, and be the butt of a joke."},
}
DEFAULT_BUDGET = 20_000


def defaults():
    return {name: {"limit": DEFAULT_BUDGET, "used": 0, "reserved": 0, "awake": False, "memories": []}
            for name in CHARACTERS}


class House:
    def __init__(self, path):
        self.path = Path(path)
        self.agents = defaults()
        self.warning = ""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for name, agent in self.agents.items():
                    saved = data.get("agents", {}).get(name, {})
                    agent["limit"] = max(256, min(1_000_000, int(saved.get("limit", DEFAULT_BUDGET))))
                    # An interrupted request may still be billed. Preserve its reservation.
                    agent["used"] = max(0, int(saved.get("used", 0))) + max(0, int(saved.get("reserved", 0)))
                    for note in saved.get("memories", [])[-30:]:
                        if isinstance(note, dict) and isinstance(note.get("text"), str):
                            agent["memories"].append({"from": str(note.get("from", "Unknown"))[:32],
                                                       "text": note["text"][:180],
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
        temporary.write_text(json.dumps({"version": 1, "agents": data}, indent=2), encoding="utf-8")
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

    def reset(self):
        self.agents = defaults()
        self.save()
