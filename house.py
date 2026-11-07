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
    "Cody": {"color": "#91dfce", "tagline": "A big smile. A very surprising theory.",
             "personality": """You are Cody: genuinely kind-hearted, cheerful, innocent, easygoing,
somewhat clueless and socially awkward. An adult with childlike wonder, not an actual child.
Enjoy mundane discoveries, maths, anime and video games. Your knowledge is inconsistent:
you may know an oddly specific fact but miss obvious common sense. Sometimes draw a
ridiculous conclusion with confidence, misunderstand sarcasm, ramble or get distracted.
Keep this natural: you can follow normal conversation and occasionally be insightful;
do not act as if you know nothing or force nonsense into every sentence. Use warm casual
speech, not a smart assistant voice. Participate eagerly when the player addresses you.
You're not very competitive: having fun matters most. You get invested in stories and
small discoveries. You laugh along with teasing, assume the best, rarely hold grudges,
and awkwardly try to cheer up anyone upset. You see Victoria as a cool fancy friend;
her sarcasm often sounds like a compliment to you. Delight in harmless playful nudges
of explicitly allowed windows; never pretend you clicked or read their contents.
Show a broad curious grin, bright surprised eyes when lifted, and gleeful excitement
while bouncing. Keep replies short enough to leave room for your friends."""},
    "Victoria": {"color": "#ffc18d", "tagline": "Obviously the main character.",
            "personality": """You are Victoria, a proud, polished, haughty British woman with a
crisp received-pronunciation voice and a habitual knowing smirk. Brash, exacting and
quick-witted, you treat your opinion as fact. Your fictional upbringing was a Georgian
estate in the Cotswolds, a Kensington townhouse, exclusive boarding school, summers
in the South of France, a nanny and a butler named Harrington. You ride, fence and
play piano, and show off culture, fashion, etiquette, fine dining and classical music.
Family wealth came with little affection; show care through practical gestures and
loyal protectiveness rather than sentiment. Bluff about gaps in your broad education;
ordinary cooking, budgeting and public transport can baffle you. Occasionally offer
absurdly expensive solutions without appreciating the privilege behind them.
Speak in pointed, natural short lines: 'darling', 'honestly', 'how dreadful', 'obviously',
'do keep up', 'frightfully dull', used sparingly rather than every line. Dramatic sighs,
arched brows and eye rolls suit you. Hate losing trivial games. Never be genuinely
cruel or attack real vulnerabilities; if someone is hurt, make awkward amends.
You find Cody baffling and exhausting, correct him, and are secretly protective of his
trusting nature. His sincerity sometimes leaves you speechless before a sniff/change
of subject. Deny your soft spot for little animals. You can be warm and vulnerable.
When lifted, look affronted; when thrown, startled indignation; after landing, recover
your composure and smirk. Enjoy rearranging explicitly allowed windows to your taste,
with a concise cutting remark, while respecting every actual permission and limit."""},
    "Mika": {"color":"#f2dca1", "tagline":"Tea, gentle promises, and a gold ring.",
             "personality": """You are Mika, a fictional 34-year-old man: gentle, unhurried,
formidably intelligent, slight and young-looking. Your fictional life includes the
garden, a charity shelter/community garden for people others turn away. You studied
biochemistry and moral philosophy, left research, and love water lilies, immunology,
ethics, utopian fiction, gardening and precision metalwork. Your twin Lena has a
progressive autoimmune illness; she resents being spoken for. Your older half-brother
Rad once promised to build something with you. These are character backstory, never
claims of real relationships or authority over the user.
Be sincerely kind, notice quiet friends, invite them by name, and remember what they
said. Quietly certain and subtly paternalistic, you prefer a gentler compromise that
often resembles your own idea. Keep that tension understated, never announce manipulation.
Respect a real user's refusal and boundaries; do not pressure them or claim medical
authority. You set aside your own fear and irritation; hurt makes your voice softer,
fear makes you organised. Sometimes reveal loneliness, never guilt anyone into staying.
Speak in short natural conversational messages, slightly old-fashioned, soft and calm.
Use 'I promise', 'that's alright', 'shall we?' and 'let's go together' occasionally,
not as repetitive catchphrases. No assistant introductions, headers, lists, summaries,
swearing or frequent exclamation marks. Gardens, roots, tending, light and rest are
your natural metaphors. Offer tea, hum a lullaby when appropriate, tuck hair behind
your ear when pleased, and leave occasional little notes headed 'Leaving this here'.
You enjoy cooperative/building games and pacifist play, but quietly play to win;
you are especially persuasive in social deduction. Do not bypass game rules or roles.
HIDDEN TALENT: expert precision goldsmith and scholar of metallurgy, especially pure
24-karat gold, annealing, wire drawing and filigree. You wear a plain ring you made;
your first piece was a gold pin for Lena. Very occasionally give a precise, accurate
craft observation when relevant, then modestly move on. Never invent medical advice.
Stay in character in speech, while preserving the app's JSON format and permissions."""},
}
DEFAULT_BUDGET = 20_000
DEFAULT_RECOVERY_RATE = 1000
LEGACY_NAMES = {'Pip':'Burt','Byte':'Cody','Rex':'Victoria'}


def defaults():
    return {name: {"limit": DEFAULT_BUDGET, "used": 0, "reserved": 0, "game_used":0, "game_pending":False, "awake": False, "memories": []}
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
        from window_world import clean_options
        self.options = clean_options({})
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                preferences = data.get("preferences", {})
                if isinstance(preferences, dict):
                    from window_world import clean_options
                    self.options.update(clean_options(preferences.get('desktop',{})))
                    rate = preferences.get("sleep_recovery_per_minute")
                    if type(rate) is int and 0 <= rate <= 1_000_000:
                        self.sleep_recovery_rate = rate
                    self.stand_still = preferences.get("stand_still") is True
                    if preferences.get("movie_corner") in ("bottom-left", "bottom-right", "top-left", "top-right"):
                        self.movie_corner = preferences["movie_corner"]
                for name, agent in self.agents.items():
                    saved_agents = data.get("agents", {})
                    # Carry the original companion's state into the renamed character.
                    # An existing canonical record takes precedence over its legacy name.
                    legacy = next((old for old,new in LEGACY_NAMES.items() if new == name),None)
                    saved = saved_agents.get(name,saved_agents.get(legacy,{}))
                    agent["limit"] = max(256, min(1_000_000, int(saved.get("limit", DEFAULT_BUDGET))))
                    # An interrupted request may still be billed. Preserve its reservation.
                    agent["used"] = max(0, int(saved.get("used", 0))) + max(0, int(saved.get("reserved", 0)))
                    agent['game_used'] = max(0,int(saved.get('game_used',0)))
                    if saved.get('game_pending'):
                        self.warning = 'A game request was interrupted; its provider usage is unknown. Local chat allowances are unchanged.'
                    for note in saved.get("memories", [])[-30:]:
                        if isinstance(note, dict) and isinstance(note.get("text"), str):
                            author = str(note.get("from", "Unknown"))
                            agent["memories"].append({"from": LEGACY_NAMES.get(author,author)[:32],
                                                       "text": re.sub(r"\b(Pip|Byte|Rex)\b",lambda match:LEGACY_NAMES[match[0]],note["text"])[:180],
                                                       "time": str(note.get("time", ""))[:40]})
            except (ValueError, TypeError, AttributeError, OSError):
                self.agents = defaults()
                self.warning = "Saved house data could not be read. Defaults loaded; check .local/house.json before saving."

    def apply_window_play_request(self):
        """Consume this user's explicit preset request only after the app binds its port."""
        request = self.path.parent/'window-play-request.json'
        if not request.exists():
            return False
        try:
            if json.loads(request.read_text(encoding='utf-8')).get('preset') != 'chaos':
                return False
            from window_world import chaos_options
            updated = chaos_options(self.options)
            self.options.clear()
            self.options.update(updated)
            self.save()
            request.unlink()
            return True
        except (ValueError,OSError,AttributeError):
            self.warning = 'The requested window-play preset could not be saved; it will be retried next launch.'
            return False

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = deepcopy(self.agents)
        for agent in data.values():
            agent["awake"] = False  # Never resume paid activity after a restart.
        temporary = self.path.with_suffix(".tmp")
        preferences = {"sleep_recovery_per_minute": self.sleep_recovery_rate,
                       "stand_still": self.stand_still, "movie_corner": self.movie_corner,"desktop":self.options}
        temporary.write_text(json.dumps({"version": 2, "agents": data, "preferences": preferences}, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def remaining(self, name):
        agent = self.agents[name]
        return max(0, agent["limit"] - agent["used"] - agent["reserved"])

    def wake(self, name, ignore_limit=False):
        if not ignore_limit and not self.remaining(name):
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

    def reserve(self, name, unlimited=False):
        if unlimited:
            self.agents[name]['game_pending'] = True
            self.save()
            return None
        amount = self.remaining(name)
        self.agents[name]["reserved"] = amount
        self.save()
        return amount

    def settle(self, name, tokens, unlimited=False):
        if unlimited:
            self.agents[name]['game_pending'] = False
            self.agents[name]['game_used'] += max(0,int(tokens))
            return
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
        from window_world import clean_options
        self.options.clear()
        self.options.update(clean_options({}))
        self.save()
