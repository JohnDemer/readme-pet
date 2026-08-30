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
# How fast it falls apart, in points per hour out of 100. These are the only
# numbers worth touching. Gentle values while nobody has found the repo yet:
# at these rates it comfortably survives a day alone and dies somewhere past
# forty hours. Roughly double them once people actually show up.
# ---------------------------------------------------------------------------
HUNGER_RATE = 2.0
THIRST_RATE = 3.0
CLEAN_RATE = 1.5
ENERGY_RATE = 1.8

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
    "love": ["pet", "hug", "love", "cuddle", "kiss", "good", "well done",
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
        "mood": None,
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
    s["hunger"] = clamp(s["hunger"] - HUNGER_RATE * hours)
    s["thirst"] = clamp(s["thirst"] - THIRST_RATE * hours)
    s["clean"] = clamp(s["clean"] - CLEAN_RATE * hours)

    if s["asleep"]:
        s["energy"] = clamp(s["energy"] + 12 * hours)
        if s["energy"] >= 100:
            s["asleep"] = False
            events.append("woke up on its own.")
    else:
        s["energy"] = clamp(s["energy"] - ENERGY_RATE * hours)

    # neglect hurts, care heals
    harm = 0
    for stat in ("hunger", "thirst"):
        if s[stat] <= 0:
            harm += 1.4 * hours
        elif s[stat] < 20:
            harm += 0.8 * hours
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
    s["mood"] = None
    if s["asleep"] and intent not in (None, "love"):
        if intent == "sleep":
            return f"{s['name']} is already asleep. You are singing to a sleeping animal."
        s["asleep"] = False
        s["bond"] = clamp(s["bond"] - 4)
        s["mood"] = "sulk"
        return f"You woke {s['name']} up. It is not delighted about it."

    if intent == "feed":
        if s["hunger"] > 88:
            s["health"] = clamp(s["health"] - 8)
            s["clean"] = clamp(s["clean"] - 10)
            s["mood"] = "sulk"
            return (f"{s['name']} eats it because you offered. Then eats it "
                    "again, in reverse, onto the floor. It did not need food.")
        s["hunger"] = clamp(s["hunger"] + 32)
        s["clean"] = clamp(s["clean"] - 4)
        s["bond"] = clamp(s["bond"] + 3)
        s["mood"] = "dance"
        return f"{s['name']} eats without breathing and looks up for more."

    if intent == "water":
        if s["thirst"] > 90:
            return f"{s['name']} sniffs the water and declines, politely."
        s["thirst"] = clamp(s["thirst"] + 38)
        s["bond"] = clamp(s["bond"] + 2)
        s["mood"] = "dance"
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
        s["mood"] = "dance"
        return f"{s['name']} plays until it falls over, which is the correct amount."

    if intent == "sleep":
        s["asleep"] = True
        s["bond"] = clamp(s["bond"] + 2)
        return f"{s['name']} curls into a shape with no clear front, and sleeps."

    if intent == "clean":
        s["clean"] = 100
        s["bond"] = clamp(s["bond"] + 2)
        s["mood"] = "sulk"
        return f"{s['name']} hates every second of this and is furious and clean."

    if intent == "love":
        s["bond"] = clamp(s["bond"] + 11)
        if s["asleep"]:
            return f"You stroke {s['name']} while it sleeps. Its tail moves once."
        s["mood"] = "dance"
        return f"{s['name']} leans its whole weight into your hand."

    if intent == "heal":
        if s["health"] > 85:
            s["health"] = clamp(s["health"] - 4)
            s["mood"] = "sulk"
            return f"{s['name']} was not ill. It is now slightly less well."
        s["health"] = clamp(s["health"] + 25)
        s["mood"] = "dance"
        return f"{s['name']} swallows the medicine and glares at you throughout."

    if intent == "scold":
        s["bond"] = clamp(s["bond"] - 12)
        s["mood"] = "sulk"
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


def status_word(v):
    if v <= 10:
        return "EMPTY"
    if v < 30:
        return "LOW"
    if v < 65:
        return "OK"
    return "GOOD"


# GitHub strips animation out of SVG files it serves from a repository, so the
# handheld is drawn as a real animated GIF instead. Slower to build, but it
# actually moves, which is the entire point.
from PIL import Image, ImageDraw, ImageFont

CANVAS = (300, 352)
CELL = 11
FONT = ImageFont.load_default()

# how the creature moves in each state: (vertical offsets, tilt in degrees)
IDLE = {
    "egg":       ([0, 0, 0, 0, 0, 0], [-4, -2, 0, 2, 4, 0]),
    "hatchling": ([0, -4, -6, -4, 0, 0], [0, 0, 0, 0, 0, 0]),
    "child":     ([0, -3, -5, -3, 0, 1], [0, 0, 0, 0, 0, 0]),
    "adult":     ([0, -2, -3, -2, 0, 0], [0, 0, 0, 0, 0, 0]),
    "elder":     ([0, -1, -2, -1, 0, 0], [0, 0, 0, 0, 0, 0]),
    "asleep":    ([0, 1, 2, 2, 1, 0], [0, 0, 0, 0, 0, 0]),
    "sick":      ([0, 1, 0, 1, 0, 1], [-2, 2, -2, 2, -1, 1]),
    "dead":      ([0, -1, -2, -3, -4, -5], [0, 0, 0, 0, 0, 0]),
}
DANCE = ([0, -9, -13, -9, 0, -6, -9, -6], [-14, -7, 0, 7, 14, 7, 0, -7])
SULK = ([0, 2, 3, 2, 0, 1], [5, 6, 5, 3, 2, 3])


def sprite_layer(grid, blink=False):
    """The creature on its own transparent layer, so it can be tilted."""
    w, h = len(grid[0]) * CELL, len(grid) * CELL
    pad = 18
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            if blink and r == 2 and ch == "o":
                continue          # eyes shut
            col = LCD_D if ch == "x" else LCD_M
            x, y = pad + c * CELL, pad + r * CELL
            d.rectangle([x, y, x + CELL - 2, y + CELL - 2], fill=col)
    return img


def draw_shell(s):
    """Everything that does not move: the plastic, the bars, the words."""
    img = Image.new("RGB", CANVAS, SHELL)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, 293, 345], radius=22, outline=SHELL_D, width=2)
    d.text((110, 24), "R E A D M E   P E T", font=FONT, fill=SHELL_D)
    d.rounded_rectangle([26, 42, 273, 255], radius=8, fill=LCD)

    for i, (label, value) in enumerate([("FED", s["hunger"]), ("WATER", s["thirst"]),
                                        ("REST", s["energy"]), ("CLEAN", s["clean"])]):
        x = 38 + i * 58
        d.text((x, 190), label, font=FONT, fill=LCD_D)
        d.rectangle([x, 201, x + 45, 207], outline=LCD_D)
        fill = int(43 * value / 100)
        if fill > 0:
            d.rectangle([x + 1, 202, x + 1 + fill, 206], fill=LCD_D)
        d.text((x, 211), status_word(value), font=FONT, fill=LCD_M)

    need = urgent(s)
    if s["dead"]:
        verdict = "GONE"
    elif s["health"] < 40 or need:
        verdict = "NEEDS " + {"thirst": "WATER", "hunger": "FOOD",
                              "energy": "SLEEP", "clean": "A WASH"}.get(need, "CARE")
    else:
        verdict = "DOING FINE"
    d.text((38, 228), verdict, font=FONT, fill=LCD_D)
    d.text((38, 240), "HEALTH %d   BOND %d   %s" %
           (s["health"], s["bond"], "ASLEEP" if s["asleep"] else "AWAKE"),
           font=FONT, fill=LCD_M)

    name = s["name"].upper()
    d.text((150 - len(name) * 3, 284), name, font=FONT, fill=INK)
    meta = "gen %d - %s - %dh old" % (s["gen"], "gone" if s["dead"] else stage(s),
                                      age_hours(s))
    d.text((150 - len(meta) * 3, 300), meta, font=FONT, fill=SHELL_D)
    for cx in (110, 150, 190):
        d.ellipse([cx - 9, 315, cx + 9, 333], fill=SHELL_D)
    return img


def render_gif(s, path="creature.gif"):
    state_name = sprite_for(s)
    grid = SPRITES[state_name]
    mood = s.get("mood") if state_name not in ("dead", "asleep") else None

    if mood == "dance":
        offsets, tilts = DANCE
        reps, hold = 3, 90
    elif mood == "sulk":
        offsets, tilts = SULK
        reps, hold = 3, 170
    else:
        offsets, tilts = IDLE[state_name]
        reps, hold = 3, 170

    shell = draw_shell(s)
    frames, n = [], len(offsets)
    total = n * reps
    for i in range(total):
        dy, tilt = offsets[i % n], tilts[i % n]
        # a blink near the end of the loop, so it is rare rather than twitchy
        blink = state_name not in ("asleep", "dead", "egg") and i == total - 3
        layer = sprite_layer(grid, blink)
        if tilt:
            layer = layer.rotate(tilt, resample=Image.BICUBIC)
        frame = shell.copy()
        px = 150 - layer.width // 2
        py = 116 - layer.height // 2 + dy
        if state_name == "dead":
            layer.putalpha(layer.getchannel("A").point(
                lambda v, k=i: int(v * max(0.25, 1 - k / total))))
        frame.paste(layer, (px, py), layer)

        d = ImageDraw.Draw(frame)
        if s["asleep"]:
            for j, (zx, zy, step) in enumerate([(230, 70, 0), (244, 60, 2), (256, 52, 4)]):
                if (i + step) % n < 4:
                    d.text((zx, zy - (i % n) * 2), "z", font=FONT, fill=LCD_D)
        if mood:
            glyph = "*" if mood == "dance" else "~"
            for j, gx in enumerate((66, 234, 50)):
                if (i + j * 2) % n < 3:
                    d.text((gx, 150 - (i % n) * 5), glyph, font=FONT, fill=LCD_D)
        if urgent(s) and not s["dead"] and i % n < n // 2:
            d.text((148, 48), "!", font=FONT, fill=LCD_D)

        frames.append(frame.convert("P", palette=Image.ADAPTIVE, colors=16))

    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=hold, loop=0, optimize=True, disposal=2)


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
    a(f'<img src="creature.gif?v={int(time.time())}" width="300" alt="{s["name"]}">')
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
    render_gif(s)
    with open("README.md", "w") as f:
        f.write(readme(s, repo))
    with open("reply.txt", "w") as f:
        f.write(reply + "\n")


if __name__ == "__main__":
    main()
