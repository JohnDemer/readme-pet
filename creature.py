"""A creature that lives in a README and talks to whoever turns up.

No images. The whole thing is text, so it always renders, everywhere, and the
Action finishes in about twenty seconds.

It ages in real time, it never names what it wants, and it has a temper: keep
doing the same thing to it and it gets annoyed, then angry, then it is sick on
the floor and refuses to speak to you for a while.

Run by .github/workflows/care.yml when someone opens an issue.
"""

import json
import os
import random
import textwrap
import time

STATE = "state.json"
COOLDOWN = 0            # seconds before the same person can act again.
                        # 0 while it is just you. Raise to ~120 once people arrive.
MAX_CHAT = 24
SULK_MINUTES = 10       # how long it hides under the table after being pushed too far

# How fast it falls apart, in points per hour out of 100. Gentle values while
# nobody has found the repo: it survives a day alone and dies past forty hours.
HUNGER_RATE = 2.0
THIRST_RATE = 3.0
CLEAN_RATE = 1.5
ENERGY_RATE = 1.8

STAGES = [(0, "egg"), (6, "hatchling"), (36, "child"), (120, "adult"), (400, "elder")]

NAMES = ["Pip", "Bubo", "Nim", "Koukou", "Tato", "Fig", "Moro", "Zuzu",
         "Pelops", "Bibi", "Gogo", "Roula", "Tsipa", "Nono"]

# ---------------------------------------------------------------------------
# what it understands. Greek included, because half the people who find this
# will type in Greek.
# ---------------------------------------------------------------------------
INTENTS = {
    "feed": ["feed", "food", "eat", "banana", "bread", "apple", "snack", "meal",
             "hungry", "dinner", "breakfast", "rice", "soup",
             "φαε", "φάε", "φαγητο", "φαγητό", "ταισε", "τάισε", "ψωμι", "ψωμί"],
    "water": ["water", "drink", "thirsty", "juice", "milk", "tea",
              "νερο", "νερό", "πιες", "διψα", "διψά"],
    "play": ["play", "game", "ball", "fun", "dance", "run", "toy", "walk",
             "παιξε", "παίξε", "παιχνιδι", "παιχνίδι", "μπαλα", "μπάλα"],
    "sleep": ["sleep", "bed", "rest", "nap", "night", "tired", "lullaby",
              "κοιμησου", "κοιμήσου", "υπνο", "ύπνο", "ξεκουρασου"],
    "clean": ["clean", "wash", "bath", "shower", "soap", "tidy", "dirty",
              "καθαρισε", "καθάρισε", "μπανιο", "μπάνιο", "πλυνε", "πλύνε"],
    "love": ["pet", "hug", "love", "cuddle", "kiss", "good", "well done",
             "scratch", "praise", "proud", "sorry", "friend",
             "αγκαλια", "αγκαλιά", "χαιδεψε", "χάιδεψε", "σαγαπω", "σ'αγαπώ"],
    "heal": ["medicine", "doctor", "pill", "heal", "cure", "vet", "bandage",
             "φαρμακο", "φάρμακο", "γιατρο", "γιατρό"],
    "scold": ["no", "bad", "stop", "shut up", "ugly", "hate", "stupid",
              "κακο", "κακό", "σκασε", "σκάσε"],
}

# ---------------------------------------------------------------------------
# its face. Same width every time so the line never jumps around.
# ---------------------------------------------------------------------------
FACES = {
    "happy":    r"""    /\_/\
   ( ^   ^ )
    >  w  <""",
    "neutral":  r"""    /\_/\
   ( o   o )
    >  -  <""",
    "hungry":   r"""    /\_/\
   ( o   o )
    >  O  <""",
    "thirsty":  r"""    /\_/\
   ( -   - )
    >  ~  <""",
    "sleepy":   r"""    /\_/\
   ( -   - )
    >  z  <""",
    "asleep":   r"""    /\_/\      z
   ( _   _ )   z
    >  _  <""",
    "dirty":    r"""    /\_/\
   ( x   o )
    > ~~~ <""",
    "sick":     r"""    /\_/\
   ( @   @ )
    >  ~  <""",
    "angry":    r"""    /\_/\
   ( >   < )
    > ### <""",
    "vomit":    r"""    /\_/\
   ( X   X )
    > ~~~~~~~""",
    "sad":      r"""    /\_/\
   ( ,   , )
    >  n  <""",
    "egg":      r"""     ____
    /    \
    \____/""",
    "dead":     r"""    /\_/\
   ( x   x )
    >  _  <""",
}

# ---------------------------------------------------------------------------
# what it says, unprompted. It has no idea what anything is called.
# ---------------------------------------------------------------------------
VOICE = {
    "thirst": ["my mouth is a cupboard.",
               "is there any of the wet thing left?",
               "i licked the wall. it was not it.",
               "i keep thinking about the bowl that shines."],
    "hunger": ["the bowl is empty in a personal way.",
               "i chewed on nothing for a while. it went badly.",
               "when is the next one? is there a next one?",
               "my middle is making an opinion."],
    "energy": ["my eyes keep closing without me.",
               "i sat down and forgot to get up.",
               "is it night? it feels like night in here.",
               "everything is heavier than this morning."],
    "clean": ["something smells and i think it is me.",
              "there is a crust behind my ear with a history.",
              "i scratched the same spot forty times.",
              "i would like to be less of whatever this is."],
    "sick": ["i feel wrong in the middle.",
             "the room is doing a slow circle.",
             "i do not want to stand up today.",
             "is this what old is?"],
    "sad": ["you were gone a long time.",
            "nobody said anything for ages.",
            "i waited by the door. there is no door.",
            "did i do something?"],
    "happy": ["you came back. good.",
              "what is outside? is it the same outside?",
              "i had a thought earlier. it was round.",
              "today is one of the better ones.",
              "if i sit here, does that count as helping?",
              "i like it when the light does that."],
    "angry": ["stop.",
              "i have said stop.",
              "you are doing it again.",
              "leave it."],
    "asleep": ["zzz", "( dreaming about the bowl )", "( one foot is twitching )"],
    "dead": ["( the screen is quiet now )", "( an egg is waiting )"],
}

SYMPTOMS = {
    "thirst": ["keeps licking the inside of its mouth.",
               "is staring at the water stain on the wall.",
               "makes a dry clicking sound when it breathes."],
    "hunger": ["is chewing on absolutely nothing.",
               "went through the empty bowl again. Twice.",
               "has gone very quiet and very still."],
    "energy": ["blinked, and the blink lasted four seconds.",
               "keeps sitting down in the middle of things.",
               "is swaying slightly, like a tired toddler."],
    "clean": ["smells like a wet coat left in a bag.",
              "has something crusty behind one ear.",
              "keeps scratching the same spot."],
    None: ["is watching you.", "seems fine, honestly.",
           "is doing a small pleased hum.", "rolled over for no reason."],
}


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def pick_name(gen):
    return NAMES[(gen * 7 + 3) % len(NAMES)]


def new_creature(gen=1, graves=None):
    now = int(time.time())
    return {
        "gen": gen, "name": pick_name(gen), "born": now, "last": now,
        "hunger": 70, "thirst": 70, "energy": 80, "clean": 90,
        "bond": 40, "health": 100,
        "asleep": False, "dead": False, "cause": "",
        "streak": {"intent": "", "count": 0},   # how many times in a row
        "sulk_until": 0,                        # hiding under the table until
        "thread": 0,                            # the issue everyone talks in
        "chat": [], "carers": [], "cooldown": {}, "graves": graves or [],
    }


def load():
    if os.path.exists(STATE):
        s = json.load(open(STATE))
        for k, v in new_creature().items():        # tolerate older state files
            s.setdefault(k, v)
        return s
    return new_creature()


def save(s):
    json.dump(s, open(STATE, "w"), indent=1)


def age_hours(s):
    return (int(time.time()) - s["born"]) / 3600.0


def stage(s):
    name = "egg"
    for hours, label in STAGES:
        if age_hours(s) >= hours:
            name = label
    return name


def clamp(v):
    return max(0, min(100, v))


def urgent(s):
    needs = [("thirst", s["thirst"]), ("hunger", s["hunger"]),
             ("energy", s["energy"]), ("clean", s["clean"])]
    needs.sort(key=lambda n: n[1])
    return needs[0][0] if needs[0][1] < 45 else None


def sulking(s):
    return int(time.time()) < s.get("sulk_until", 0)


def face(s):
    if s["dead"]:
        return FACES["dead"]
    if sulking(s):
        return FACES["angry"]
    if s["asleep"]:
        return FACES["asleep"]
    if s["health"] < 45:
        return FACES["sick"]
    if stage(s) == "egg":
        return FACES["egg"]
    need = urgent(s)
    if need:
        return FACES[{"thirst": "thirsty", "hunger": "hungry",
                      "energy": "sleepy", "clean": "dirty"}[need]]
    if s["bond"] < 25:
        return FACES["sad"]
    if s["bond"] > 65:
        return FACES["happy"]
    return FACES["neutral"]


def mood_word(s):
    if s["dead"]:
        return "gone"
    if sulking(s):
        return "furious with you"
    if s["asleep"]:
        return "asleep"
    if s["health"] < 45:
        return "unwell"
    need = urgent(s)
    if need:
        return {"thirst": "thirsty", "hunger": "hungry",
                "energy": "exhausted", "clean": "filthy"}[need]
    if s["bond"] < 25:
        return "lonely"
    if s["bond"] > 65:
        return "content"
    return "alright"


# ---------------------------------------------------------------------------
# time passing, whether anyone visits or not
# ---------------------------------------------------------------------------
def tick(s):
    now = int(time.time())
    hours = (now - s["last"]) / 3600.0
    s["last"] = now
    if s["dead"] or hours <= 0:
        return []

    events = []
    s["hunger"] = clamp(s["hunger"] - HUNGER_RATE * hours)
    s["thirst"] = clamp(s["thirst"] - THIRST_RATE * hours)
    s["clean"] = clamp(s["clean"] - CLEAN_RATE * hours)

    if s["asleep"]:
        s["energy"] = clamp(s["energy"] + 12 * hours)
        if s["energy"] >= 100:
            s["asleep"] = False
            events.append("woke up on its own while nobody was here.")
    else:
        s["energy"] = clamp(s["energy"] - ENERGY_RATE * hours)

    if hours > 6:
        s["bond"] = clamp(s["bond"] - 1.5 * (hours / 6))

    harm = 0
    for stat in ("hunger", "thirst"):
        if s[stat] <= 0:
            harm += 1.4 * hours
        elif s[stat] < 20:
            harm += 0.8 * hours
    if s["clean"] <= 5:
        harm += 0.8 * hours
    if harm == 0 and s["hunger"] > 50 and s["thirst"] > 50:
        s["health"] = clamp(s["health"] + 3 * hours)
    s["health"] = clamp(s["health"] - harm)

    if s["health"] <= 0:
        kill(s, "neglect")
        events.append("did not make it.")
    return events


def kill(s, cause):
    s["dead"] = True
    s["cause"] = cause
    s["graves"].insert(0, {"gen": s["gen"], "name": s["name"],
                           "hours": round(age_hours(s), 1), "cause": cause,
                           "carers": len(s["carers"])})
    s["graves"] = s["graves"][:8]


def hatch_new(s):
    graves, chat = s["graves"], s["chat"][-6:]
    fresh = new_creature(s["gen"] + 1, graves)
    fresh["chat"] = chat
    return fresh


# ---------------------------------------------------------------------------
# understanding people
# ---------------------------------------------------------------------------
def read_intent(text):
    t = " " + text.lower().strip() + " "
    hits = []
    for intent, words in INTENTS.items():
        for w in words:
            if w in t:
                hits.append((t.index(w), intent))
                break
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def push_streak(s, intent):
    """How many times in a row the same thing has been done to it."""
    if intent and s["streak"]["intent"] == intent:
        s["streak"]["count"] += 1
    else:
        s["streak"] = {"intent": intent or "", "count": 1}
    return s["streak"]["count"]


def be_sick(s, why):
    """The limit. It throws up, and then it will not talk to anyone."""
    s["hunger"] = clamp(s["hunger"] - 40)
    s["clean"] = clamp(s["clean"] - 35)
    s["health"] = clamp(s["health"] - 10)
    s["bond"] = clamp(s["bond"] - 15)
    s["asleep"] = False
    s["sulk_until"] = int(time.time()) + SULK_MINUTES * 60
    s["streak"] = {"intent": "", "count": 0}
    return (f"{s['name']} makes a noise nobody wants to hear and is sick on the "
            f"floor. {why} It goes under the table and will not come out for "
            f"{SULK_MINUTES} minutes.")


def act(s, intent, who):
    name = s["name"]

    if sulking(s):
        left = (s["sulk_until"] - int(time.time())) // 60 + 1
        if intent == "love":
            s["sulk_until"] -= 120
            s["bond"] = clamp(s["bond"] + 4)
            return f"{name} does not come out, but the tail moves once. ({left} min)"
        return (f"{name} is under the table and is not interested in you right "
                f"now. Try again in about {left} minutes.")

    count = push_streak(s, intent)

    # the temper: three is a warning, four is anger, five is the floor
    if intent in ("feed", "water", "play", "clean", "heal") and count >= 3:
        if count == 3:
            s["bond"] = clamp(s["bond"] - 3)
            return f"{name} stops and looks at you. That is the third time in a row."
        if count == 4:
            s["bond"] = clamp(s["bond"] - 8)
            return f"{name} bares its teeth slightly. It is not playing. Stop."
        return be_sick(s, "You would not stop.")

    if s["asleep"] and intent not in (None, "love"):
        if intent == "sleep":
            return f"{name} is already asleep. You are singing to a sleeping animal."
        s["asleep"] = False
        s["bond"] = clamp(s["bond"] - 4)
        return f"You woke {name} up. It is not delighted about it."

    if intent == "feed":
        if s["hunger"] > 88:
            # a refusal first. Only if you insist does it end badly.
            if count < 3:
                s["bond"] = clamp(s["bond"] - 2)
                return f"{name} turns its head away from the bowl. It is full."
            return be_sick(s, "It was full and it told you so.")
        s["hunger"] = clamp(s["hunger"] + 32)
        s["clean"] = clamp(s["clean"] - 4)
        s["bond"] = clamp(s["bond"] + 3)
        return f"{name} eats without breathing and looks up for more."

    if intent == "water":
        if s["thirst"] > 92:
            return f"{name} sniffs the water and declines, politely."
        s["thirst"] = clamp(s["thirst"] + 38)
        s["bond"] = clamp(s["bond"] + 2)
        return f"{name} drinks for a long time, then sneezes."

    if intent == "play":
        if s["energy"] < 20:
            s["energy"] = clamp(s["energy"] - 6)
            s["bond"] = clamp(s["bond"] - 2)
            return f"{name} tries to play, gets up, and sits back down."
        s["energy"] = clamp(s["energy"] - 14)
        s["hunger"] = clamp(s["hunger"] - 6)
        s["clean"] = clamp(s["clean"] - 6)
        s["bond"] = clamp(s["bond"] + 9)
        return f"{name} plays until it falls over, which is the correct amount."

    if intent == "sleep":
        s["asleep"] = True
        s["bond"] = clamp(s["bond"] + 2)
        return f"{name} curls into a shape with no clear front, and sleeps."

    if intent == "clean":
        if s["clean"] > 90:
            s["bond"] = clamp(s["bond"] - 5)
            return f"{name} was already clean and now it is wet and insulted."
        s["clean"] = 100
        s["bond"] = clamp(s["bond"] + 2)
        return f"{name} hates every second of this and is furious and clean."

    if intent == "love":
        s["bond"] = clamp(s["bond"] + 11)
        if s["asleep"]:
            return f"You stroke {name} while it sleeps. Its tail moves once."
        return f"{name} leans its whole weight into your hand."

    if intent == "heal":
        if s["health"] > 85:
            s["health"] = clamp(s["health"] - 4)
            return f"{name} was not ill, and is now slightly less well than before."
        s["health"] = clamp(s["health"] + 25)
        return f"{name} swallows it and glares at you throughout."

    if intent == "scold":
        s["bond"] = clamp(s["bond"] - 12)
        return f"{name} does not know the words but understood the tone."

    s["bond"] = clamp(s["bond"] + 1)
    return f"{name} does not understand, but " + random.choice(SYMPTOMS[urgent(s)])


def says(s):
    """One unprompted line, from how it feels right now."""
    if s["dead"]:
        pool = VOICE["dead"]
    elif sulking(s):
        pool = VOICE["angry"]
    elif s["asleep"]:
        pool = VOICE["asleep"]
    elif s["health"] < 45:
        pool = VOICE["sick"]
    elif urgent(s):
        pool = VOICE[urgent(s)]
    elif s["bond"] < 25:
        pool = VOICE["sad"]
    else:
        pool = VOICE["happy"]
    rng = random.Random(int(s["last"]) // 37 + int(s["bond"]) + s["gen"])
    return rng.choice(pool)


def log(s, who, said, reply):
    s["chat"].append({"t": int(time.time()), "who": who, "said": said, "reply": reply})
    s["chat"] = s["chat"][-MAX_CHAT:]


def care(s, text, who):
    events = tick(s)
    for e in events:
        log(s, "", "", f"( {e} )")

    if s["dead"]:
        old = s["name"]
        s.update(hatch_new(s))
        reply = f"{old} is gone. An egg was already waiting. This one is {s['name']}."
        log(s, "", "", reply)
        return reply, True

    now = int(time.time())
    if COOLDOWN and now - s["cooldown"].get(who, 0) < COOLDOWN:
        wait = (COOLDOWN - (now - s["cooldown"][who])) // 60 + 1
        return f"Someone else's turn. Come back in about {wait} minutes.", False

    reply = act(s, read_intent(text), who)
    s["cooldown"][who] = now
    s["cooldown"] = {k: v for k, v in s["cooldown"].items()
                     if now - v < max(COOLDOWN, 60) * 6}
    if who not in s["carers"]:
        s["carers"].append(who)

    if s["health"] <= 0 and not s["dead"]:
        kill(s, "care that came too late")
        reply += f" {s['name']} does not get up again."

    log(s, who, text.strip()[:140], reply)
    return reply, True


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------
def ago(t):
    d = int(time.time()) - t
    if d < 90:
        return "just now"
    if d < 5400:
        return f"{d // 60} min ago"
    if d < 172800:
        return f"{d // 3600}h ago"
    return f"{d // 86400}d ago"


def meter(value):
    full = int(round(value / 10))
    return "\u2588" * full + "\u2591" * (10 - full)


def readme(s, repo):
    thread = s.get("thread") or 1
    room = f"https://github.com/{repo}/issues/{thread}"

    L = []
    a = L.append
    a(f"# {s['name']}")
    a("")
    a("```")
    a(face(s))
    a("```")
    a("")
    a(f"**{s['name']}:** \u201c{says(s)}\u201d")
    a("")
    a(f"*{'gone' if s['dead'] else stage(s)} \u00b7 gen {s['gen']} \u00b7 "
      f"{age_hours(s):.0f} hours old \u00b7 currently **{mood_word(s)}***")
    a("")
    a("```")
    a(f"food   {meter(s['hunger'])}  water  {meter(s['thirst'])}")
    a(f"rest   {meter(s['energy'])}  clean  {meter(s['clean'])}")
    a(f"health {meter(s['health'])}  bond   {meter(s['bond'])}")
    a("```")
    a("")
    a(f"## \u27a4 [Talk to {s['name']} here]({room})")
    a("")
    a(f"That opens the one thread everybody uses. Type a message in the box at "
      f"the bottom, press Comment, and {s['name']} answers you underneath within "
      "about half a minute. No titles, no forms, nothing to fill in.")
    a("")
    a("It understands food, water, play, sleep, washing, kindness and medicine \u2014 "
      "in English or Greek \u2014 and it replies to everything else too, in its own way.")
    a("")
    a("> It never says what it needs outright. Read what it says, check the bars, "
      "and don't do the same thing over and over \u2014 it has a limit, and you "
      "will find it.")
    a("")
    a("## The conversation")
    a("")
    if s["chat"]:
        for m in reversed(s["chat"]):
            if m["who"]:
                a(f"**{m['who']}** \u2014 *{ago(m['t'])}*")
                a("")
                a(f"> {m['said']}")
                a("")
                a(f"**{s['name']}:** {m['reply']}")
            else:
                a(f"*{m['reply']}* \u2014 *{ago(m['t'])}*")
            a("")
            a("---")
            a("")
    else:
        a("*Nothing yet. It is waiting.*")
        a("")
    a(f"*{len(s['carers'])} people have talked to this one.*")
    a("")

    if s["graves"]:
        a("## The ones before")
        a("")
        a("| Gen | Name | Lived | Died of | People |")
        a("|---:|---|---:|---|---:|")
        for g in s["graves"]:
            a(f"| {g['gen']} | {g['name']} | {g['hours']}h | {g['cause']} | "
              f"{g['carers']} |")
        a("")

    a("<details><summary>How it works</summary>")
    a("")
    a("Opening an issue runs a GitHub Action. It reads `state.json`, ages the "
      "creature by exactly the time that has passed since the last visitor, matches "
      "your sentence against a list of intents, applies it, rewrites this page, "
      "then replies to your issue and closes it. No server, no images. The "
      "repository is the pet.")
    a("")
    a("Overfeeding makes it sick. So does the same action three times in a row: a "
      "warning, then anger, then it throws up and hides under the table for ten "
      "minutes. If nobody comes for long enough it dies, permanently, and an egg "
      "takes its place.")
    a("")
    a("</details>")
    a("")
    return "\n".join(L) + "\n"


def main():
    # A comment in the chat thread is the normal way in. Opening an issue still
    # works, so the very first message can create the thread.
    text = (os.environ.get("COMMENT_BODY") or os.environ.get("ISSUE_TITLE") or "").strip()
    who = "@" + os.environ.get("ISSUE_ACTOR", "someone")
    repo = os.environ.get("GITHUB_REPOSITORY", "USER/readme-pet")
    number = os.environ.get("ISSUE_NUMBER", "")

    s = load()
    if number.isdigit() and not s.get("thread"):
        s["thread"] = int(number)
    if text:
        reply, _ = care(s, text, who)
    else:
        for e in tick(s):
            log(s, "", "", f"( nobody came. It {e} )")
        reply = "time passed"

    save(s)
    open("README.md", "w").write(readme(s, repo))
    open("reply.txt", "w").write(reply + "\n")


if __name__ == "__main__":
    main()
