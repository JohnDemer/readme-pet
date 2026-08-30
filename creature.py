"""A creature that lives in a README and is kept alive by strangers.

Everything is in this one file on purpose: state, ageing, understanding what
people wrote, drawing the handheld, and rebuilding the README. Two files is
the whole project, so it can be created in the GitHub web editor without ever
touching git.

Run by .github/workflows/care.yml when someone opens an issue.
"""

import json
import os
import random
import sys
import time

STATE = "state.json"
COOLDOWN = 300          # seconds before the same person can act again
MAX_CHAT = 14

# ---------------------------------------------------------------------------
# what the creature understands. Greek included, because half the people who
# find this will type in Greek.
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
    "love": ["pet", "hug", "love", "cuddle", "kiss", "good boy", "good girl",
             "scratch", "praise", "proud", "sorry",
             "αγκαλια", "αγκαλιά", "χαιδεψε", "χάιδεψε", "σαγαπω", "σ'αγαπώ"],
    "heal": ["medicine", "doctor", "pill", "heal", "cure", "vet", "bandage",
             "φαρμακο", "φάρμακο", "γιατρο", "γιατρό"],
    "scold": ["no", "bad", "stop", "shut up", "ugly", "hate", "stupid",
              "κακο", "κακό", "σκασε", "σκάσε"],
}

STAGES = [(0, "egg"), (6, "hatchling"), (36, "child"), (120, "adult"), (400, "elder")]

# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def new_creature(gen=1, graves=None):
    return {
        "gen": gen,
        "name": pick_name(gen),
        "born": int(time.time()),
        "last": int(time.time()),
        "hunger": 70, "thirst": 70, "energy": 80, "clean": 90,
        "bond": 40, "health": 100,
        "asleep": False,
        "dead": False,
        "cause": "",
        "chat": [],
        "carers": [],
        "cooldown": {},
        "graves": graves or [],
    }


NAMES = ["Pip", "Bubo", "Nim", "Koukou", "Tato", "Fig", "Moro", "Zuzu",
         "Pelops", "Bibi", "Gogo", "Roula", "Tsipa", "Nono"]


def pick_name(gen):
    return NAMES[(gen * 7 + 3) % len(NAMES)]


def load():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return new_creature()


def save(s):
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


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


# ---------------------------------------------------------------------------
# time passing. This is the whole point: it decays whether anyone visits or not.
# ---------------------------------------------------------------------------
def tick(s):
    now = int(time.time())
    hours = (now - s["last"]) / 3600.0
    s["last"] = now
    if s["dead"] or hours <= 0:
        return []

    events = []
    s["hunger"] = clamp(s["hunger"] - 5.5 * hours)
    s["thirst"] = clamp(s["thirst"] - 7.5 * hours)
    s["clean"] = clamp(s["clean"] - 3.0 * hours)

    if s["asleep"]:
        s["energy"] = clamp(s["energy"] + 12 * hours)
        if s["energy"] >= 100:
            s["asleep"] = False
            events.append("woke up on its own.")
    else:
        s["energy"] = clamp(s["energy"] - 3.5 * hours)

    # neglect hurts, care heals
    harm = 0
    for stat in ("hunger", "thirst"):
        if s[stat] <= 0:
            harm += 5 * hours
        elif s[stat] < 20:
            harm += 1.5 * hours
    if s["clean"] <= 5:
        harm += 1.5 * hours
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
    s["graves"].insert(0, {
        "gen": s["gen"], "name": s["name"],
        "hours": round(age_hours(s), 1),
        "cause": cause,
        "carers": len(s["carers"]),
    })
    s["graves"] = s["graves"][:8]


def hatch_new(s):
    graves, chat = s["graves"], s["chat"][-4:]
    fresh = new_creature(s["gen"] + 1, graves)
    fresh["chat"] = chat + [{"who": "", "said": "", "reply":
                             f"A new egg appears. This one is called {fresh['name']}."}]
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


def urgent(s):
    """What it needs most. It never says this outright — it only shows it."""
    needs = [("thirst", s["thirst"]), ("hunger", s["hunger"]),
             ("energy", s["energy"]), ("clean", s["clean"])]
    needs.sort(key=lambda n: n[1])
    worst, value = needs[0]
    return worst if value < 45 else None


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


def act(s, intent, text, who):
    """Apply what someone did. Returns the creature's reply."""
    if s["asleep"] and intent not in (None, "love"):
        if intent == "sleep":
            return f"{s['name']} is already asleep. You are singing to a sleeping animal."
        s["asleep"] = False
        s["bond"] = clamp(s["bond"] - 4)
        return f"You woke {s['name']} up. It is not delighted about it."

    if intent == "feed":
        if s["hunger"] > 88:
            s["health"] = clamp(s["health"] - 8)
            s["clean"] = clamp(s["clean"] - 10)
            return (f"{s['name']} eats it because you offered. Then eats it again, "
                    "in reverse, onto the floor. It did not need more food.")
        s["hunger"] = clamp(s["hunger"] + 32)
        s["clean"] = clamp(s["clean"] - 4)
        s["bond"] = clamp(s["bond"] + 3)
        return f"{s['name']} eats without breathing and looks up for more."

    if intent == "water":
        if s["thirst"] > 90:
            return f"{s['name']} sniffs the water and declines, politely."
        s["thirst"] = clamp(s["thirst"] + 38)
        s["bond"] = clamp(s["bond"] + 2)
        return f"{s['name']} drinks for a long time, then sneezes."

    if intent == "play":
        if s["energy"] < 20:
            s["energy"] = clamp(s["energy"] - 6)
            s["bond"] = clamp(s["bond"] - 2)
            return f"{s['name']} tries to play, gets up, and sits back down."
        s["energy"] = clamp(s["energy"] - 14)
        s["hunger"] = clamp(s["hunger"] - 6)
        s["bond"] = clamp(s["bond"] + 9)
        s["clean"] = clamp(s["clean"] - 6)
        return f"{s['name']} plays until it falls over, which is the correct amount."

    if intent == "sleep":
        s["asleep"] = True
        s["bond"] = clamp(s["bond"] + 2)
        return f"{s['name']} curls into a shape with no clear front, and sleeps."

    if intent == "clean":
        s["clean"] = 100
        s["bond"] = clamp(s["bond"] + 2)
        return f"{s['name']} hates every second of this and is furious and clean."

    if intent == "love":
        s["bond"] = clamp(s["bond"] + 11)
        if s["asleep"]:
            return f"You stroke {s['name']} while it sleeps. Its tail moves once."
        return f"{s['name']} leans its whole weight into your hand."

    if intent == "heal":
        if s["health"] > 85:
            s["health"] = clamp(s["health"] - 4)
            return f"{s['name']} was not ill. It is now slightly less well than before."
        s["health"] = clamp(s["health"] + 25)
        return f"{s['name']} swallows the medicine and glares at you throughout."

    if intent == "scold":
        s["bond"] = clamp(s["bond"] - 12)
        return f"{s['name']} does not know the words but understood the tone."

    s["bond"] = clamp(s["bond"] + 1)
    need = urgent(s)
    return f"{s['name']} does not understand, but " + random.choice(SYMPTOMS[need])


def care(s, text, who):
    """One interaction. Returns (reply, accepted)."""
    events = tick(s)

    if s["dead"]:
        s.update(hatch_new(s))
        return (f"{s['graves'][0]['name']} is gone. An egg was already waiting. "
                f"Say hello to {s['name']}."), True

    now = int(time.time())
    last = s["cooldown"].get(who, 0)
    if now - last < COOLDOWN:
        wait = (COOLDOWN - (now - last)) // 60 + 1
        return (f"You have done enough for now. Someone else's turn — "
                f"come back in about {wait} minutes."), False

    intent = read_intent(text)
    reply = act(s, intent, text, who)
    s["cooldown"][who] = now
    s["cooldown"] = {k: v for k, v in s["cooldown"].items() if now - v < COOLDOWN * 6}
    if who not in s["carers"]:
        s["carers"].append(who)

    if s["health"] <= 0 and not s["dead"]:
        kill(s, "care that came too late")
        reply += f" {s['name']} does not get up again."

    s["chat"].append({"who": who, "said": text.strip()[:120], "reply": reply})
    s["chat"] = s["chat"][-MAX_CHAT:]
    for e in events:
        s["chat"].append({"who": "", "said": "", "reply": f"(while nobody was here, it {e})"})
    s["chat"] = s["chat"][-MAX_CHAT:]
    return reply, True


# ---------------------------------------------------------------------------
# the handheld
# ---------------------------------------------------------------------------
SHELL, SHELL_D = "#d8cdb8", "#b3a68c"
LCD, LCD_D, LCD_M = "#a8b84a", "#1e2a10", "#5c6b22"
INK = "#2a2419"

SPRITES = {
    "egg": ["....xxxx....", "..xx....xx..", ".x........x.", "x..oo..oo..x",
            "x..........x", "x...o..o...x", "x..........x", ".x........x.",
            "..xx....xx..", "....xxxx...."],
    "hatchling": ["....xxxx....", "...x....x...", "..x.o..o.x..", "..x......x..",
                  "..x..oo..x..", "...x....x...", "..xxxxxxxx..", ".x..x..x..x.",
                  "....x..x....", "...xx..xx..."],
    "child": ["..x......x..", "...x....x...", "..xxxxxxxx..", ".x.o....o.x.",
              "x..........x", "x....oo....x", "x..........x", ".xxxxxxxxxx.",
              "..x.x..x.x..", "..x.x..x.x.."],
    "adult": [".x........x.", "..xxxxxxxx..", ".x.o....o.x.", "x..........x",
              "x...o..o...x", "x....oo....x", "x..........x", "x..........x",
              ".xxxxxxxxxx.", "..xx....xx.."],
    "elder": ["..xxxxxxxx..", ".x........x.", "x..oo..oo..x", "x..........x",
              "x...oooo...x", "x..........x", ".x........x.", "..xxxxxxxx..",
              "..x......x..", ".xx......xx."],
    "asleep": ["............", "..xxxxxxxx..", ".x........x.", "x..oo..oo..x",
               "x..........x", "x....oo....x", "x..........x", ".xxxxxxxxxx.",
               "............", "............"],
    "sick": ["..xxxxxxxx..", ".x........x.", "x.o.o..o.o.x", "x..........x",
             "x..o.oo.o..x", "x..........x", ".x........x.", "..xxxxxxxx..",
             "...x....x...", "...x....x..."],
    "dead": ["....xxxx....", "..xx....xx..", ".x..o..o..x.", "x..........x",
             "x...oooo...x", "x..........x", "x.o.o.o.o.ox", ".x........x.",
             "..x.x..x.x..", "..x..x..x..."],
}


def sprite_for(s):
    if s["dead"]:
        return "dead"
    if s["asleep"]:
        return "asleep"
    if s["health"] < 45:
        return "sick"
    return stage(s)


def bar(x, y, value, label, out):
    w = 46
    fill = int(w * value / 100)
    out.append(f'<text x="{x}" y="{y - 3}" font-size="7" fill="{LCD_D}" '
               f'font-family="monospace">{label}</text>')
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="6" fill="none" '
               f'stroke="{LCD_D}" stroke-width="1"/>')
    if fill > 1:
        out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{fill - 2}" height="4" '
                   f'fill="{LCD_D}"/>')


def render(s):
    o = []
    a = o.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="330" '
      'viewBox="0 0 300 330" font-family="ui-monospace,monospace">')

    a(f'<rect width="300" height="330" rx="26" fill="{SHELL}"/>')
    a(f'<rect x="6" y="6" width="288" height="318" rx="22" fill="none" '
      f'stroke="{SHELL_D}" stroke-width="2"/>')
    a(f'<text x="150" y="30" font-size="10" fill="{SHELL_D}" text-anchor="middle" '
      f'letter-spacing="4">README PET</text>')

    # screen
    a(f'<rect x="26" y="42" width="248" height="196" rx="8" fill="{LCD}"/>')
    a(f'<rect x="26" y="42" width="248" height="196" rx="8" fill="none" '
      f'stroke="{LCD_D}" stroke-width="2" opacity=".5"/>')

    # creature, drawn big and blocky in the middle of the screen
    grid = SPRITES[sprite_for(s)]
    cell = 11
    ox = 150 - (len(grid[0]) * cell) / 2
    oy = 64
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            col = LCD_D if ch == "x" else LCD_M
            a(f'<rect x="{ox + c * cell}" y="{oy + r * cell}" width="{cell - 1}" '
              f'height="{cell - 1}" fill="{col}"/>')

    if s["asleep"]:
        a(f'<text x="238" y="72" font-size="14" fill="{LCD_D}">z</text>')
        a(f'<text x="250" y="62" font-size="10" fill="{LCD_M}">z</text>')

    # needs, along the bottom of the screen
    bar(38, 202, s["hunger"], "FED", o)
    bar(96, 202, s["thirst"], "WATER", o)
    bar(154, 202, s["energy"], "REST", o)
    bar(212, 202, s["clean"], "CLEAN", o)
    a(f'<text x="38" y="228" font-size="8" fill="{LCD_D}">HEALTH {int(s["health"])}'
      f'  BOND {int(s["bond"])}</text>')

    # plastic below the screen
    label = "gone" if s["dead"] else stage(s)
    a(f'<text x="150" y="264" font-size="15" fill="{INK}" text-anchor="middle" '
      f'font-weight="700" letter-spacing="2">{s["name"].upper()}</text>')
    a(f'<text x="150" y="280" font-size="9" fill="{SHELL_D}" text-anchor="middle">'
      f'gen {s["gen"]} \u00b7 {label} \u00b7 {age_hours(s):.0f}h old</text>')
    for i, cx in enumerate((110, 150, 190)):
        a(f'<circle cx="{cx}" cy="302" r="9" fill="{SHELL_D}"/>')
    a('</svg>')
    return "".join(o)


# ---------------------------------------------------------------------------
# the page
# ---------------------------------------------------------------------------
def readme(s, repo):
    import urllib.parse
    def new_issue(label, text):
        q = urllib.parse.urlencode({"title": text, "body":
                                    "Write anything you like as the title. Then press Create."})
        return f"[{label}](https://github.com/{repo}/issues/new?{q})"

    L = []
    a = L.append
    a(f"# {s['name']} is alive because strangers keep it alive")
    a("")
    a("It gets hungry in real time, whether or not anyone is looking. "
      "It never tells you what it needs — you have to read it. "
      "Write to it and it does what you said, including when what you said is wrong.")
    a("")
    a(f'<img src="creature.svg?v={int(time.time())}" width="300" alt="{s["name"]}">')
    a("")
    a("### Say something to it")
    a("")
    a(f"{new_issue('give it food', 'here, eat this')} · "
      f"{new_issue('give it water', 'have some water')} · "
      f"{new_issue('play with it', 'lets play')} · "
      f"{new_issue('put it to bed', 'go to sleep')} · "
      f"{new_issue('clean it', 'time for a bath')} · "
      f"{new_issue('be kind to it', 'you are a good one')}")
    a("")
    a(f"Or [**write your own words**](https://github.com/{repo}/issues/new) — "
      "put the sentence in the **title**, leave the body empty. It understands "
      "English and Greek, and it answers everything.")
    a("")
    a("### What it looks like right now")
    a("")
    need = urgent(s)
    a(f"> {s['name']} " + random.choice(SYMPTOMS[need]))
    a("")
    a("### The conversation so far")
    a("")
    if s["chat"]:
        for m in reversed(s["chat"]):
            if m["who"]:
                a(f"**{m['who']}:** {m['said']}  ")
                a(f"*{m['reply']}*")
            else:
                a(f"*{m['reply']}*")
            a("")
    else:
        a("*Nobody has said anything yet.*")
        a("")
    a(f"{len(s['carers'])} people have looked after this one.")
    a("")
    if s["graves"]:
        a("### The ones before")
        a("")
        a("| Gen | Name | Lived | Died of | Carers |")
        a("|---:|---|---:|---|---:|")
        for g in s["graves"]:
            a(f"| {g['gen']} | {g['name']} | {g['hours']}h | {g['cause']} | {g['carers']} |")
        a("")
    a("---")
    a("")
    a("<details><summary>How it works</summary>")
    a("")
    a("Opening an issue runs a GitHub Action. It reads `state.json`, works out how "
      "much time has passed since the last visitor and decays the creature by that "
      "much, matches your words against a list of intents, applies the effect, "
      "redraws the handheld, rewrites this page, then replies to your issue and "
      "closes it. No server. The repository is the pet.")
    a("")
    a("Overfeeding hurts it. Medicine when it is well hurts it. Waking it hurts it. "
      "The needs bars are the only honest information you get.")
    a("")
    a("</details>")
    a("")
    return "\n".join(L) + "\n"


def main():
    text = os.environ.get("ISSUE_TITLE", "").strip()
    who = "@" + os.environ.get("ISSUE_ACTOR", "someone")
    repo = os.environ.get("GITHUB_REPOSITORY", "USER/readme-pet")

    s = load()
    if text:
        reply, _ = care(s, text, who)
    else:
        # scheduled run: time passes, nobody said anything
        events = tick(s)
        for e in events:
            s["chat"].append({"who": "", "said": "", "reply": f"(nobody came. It {e})"})
        s["chat"] = s["chat"][-MAX_CHAT:]
        reply = "time passed"

    save(s)
    with open("creature.svg", "w") as f:
        f.write(render(s))
    with open("README.md", "w") as f:
        f.write(readme(s, repo))
    with open("reply.txt", "w") as f:
        f.write(reply + "\n")


if __name__ == "__main__":
    main()
