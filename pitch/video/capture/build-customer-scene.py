"""Generates compositions/customer.html (scene 5, the customer side) from the capture + its pointer log.

  python capture/build-customer-scene.py

The clip is cut into segments (capture seconds -> film seconds, with a constant speed each). Everything that depends on the
capture clock (camera, pointer, step ticker) is a pure function of film time, derived from the same table, so editing a
segment or a camera key re-times all of it.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ev = json.load(open(os.path.join(HERE, "out", "customer.events.json"), encoding="utf-8"))

# (capture start, capture end, speed)
SEGMENTS = [
    (0.8, 4.2, 1.5),    # homepage, click "Plan my home", the advisor sheet opens
    (6.0, 10.4, 2.0),   # step 1: yearly use, typed, Next
    (10.4, 11.4, 1.3),  # step 1 -> 2 transition
    (12.8, 17.6, 2.4),  # step 2: address typed, Find roof
    (17.6, 20.9, 1.8),  # roof found, "Your roof" glows
    (20.9, 24.0, 1.6),  # step 3: car planned, car and wallbox appear
    (24.6, 28.4, 1.8),  # step 4: heating gas, results begin
    (28.4, 31.0, 1.2),  # results settle, the house builds
    (31.0, 37.6, 1.3),  # price, savings tapped, the advisor explains
    (43.1, 50.9, 3.0),  # send plan: name typed, Send plan
    (50.9, 55.0, 1.5),  # back to the top, the sent confirmation
]

# camera keys: capture time of ARRIVAL, zoom, centre in capture css px, film seconds the move takes
CAMERA = [
    (0.8, 1.0, (720, 450), 0.0),
    (6.8, 1.6, (1020, 520), 0.8),    # push to the step card
    (18.4, 1.35, (330, 420), 0.6),   # pan to the house: "Your roof" glows
    (21.3, 1.3, (700, 470), 0.9),    # car + heating tiles, house in view
    (27.8, 1.0, (720, 450), 1.0),    # results: the whole page
    (31.7, 1.8, (330, 690), 1.0),    # the price range, marked estimate
    (34.7, 1.7, (330, 720), 0.6),    # price + savings tile
    (36.7, 1.45, (300, 470), 0.8),   # the advisor's explanation on the house
    (43.9, 1.5, (516, 740), 0.25),    # name field and Send plan
    (52.9, 1.0, (720, 450), 0.9),    # the whole page: sent
]

# the ticker follows what the screen shows, which trails the logged step marks by ~0.5 s (the card slides in after the click)
STEP_MARKS = [("Usage", 4.0), ("Address", 10.9), ("Car", 21.5), ("Heating", 22.6)]
RESULTS_AT = 26.5

# ---- derived tables ----------------------------------------------------------------------------------------------------
film0 = 0.0
segs = []
for c0, c1, r in SEGMENTS:
    dur = (c1 - c0) / r
    segs.append({"cap0": c0, "cap1": c1, "rate": r, "film0": round(film0, 4), "dur": round(dur, 4)})
    film0 += dur
TOTAL = round(film0, 3)

pointer = []  # [[capT0, capT1, [x0,y0], [x1,y1]]]
downs = []
last_move = None
for e in ev["events"]:
    if e["kind"] == "move":
        last_move = e
    elif e["kind"] == "arrive" and last_move:
        pointer.append([last_move["t"], e["t"], last_move["from"], last_move["to"]])
        last_move = None
    elif e["kind"] == "down":
        downs.append(e["t"])

PAGE_W, PAGE_H = ev["width"], ev["height"]
mp4_rel = "assets/customer-capture.mp4"

clips = []
for i, s in enumerate(segs):
    hold = 1.7 if i == len(segs) - 1 else 0  # the last frame stays on screen through the hand-off
    clips.append(
        f'    <video id="c5-v{i}" class="clip c5-vid" src="{mp4_rel}" muted playsinline data-start="{s["film0"]}" data-duration="{round(s["dur"] + hold, 4)}" '
        f'data-media-start="{s["cap0"]}" data-playback-rate="{s["rate"]}" data-track-index="{i}"></video>'
    )

html = open(os.path.join(HERE, "customer.template.html"), encoding="utf-8").read()
html = (html
        .replace("/*VIDEOS*/", "\n".join(clips))
        .replace("/*SEGMENTS*/", json.dumps(segs))
        .replace("/*CAMERA*/", json.dumps(CAMERA))
        .replace("/*POINTER*/", json.dumps(pointer))
        .replace("/*DOWNS*/", json.dumps(downs))
        .replace("/*STEPS*/", json.dumps(STEP_MARKS))
        .replace("/*RESULTS_AT*/", str(RESULTS_AT))
        .replace("/*TOTAL*/", str(TOTAL)))
out = os.path.join(ROOT, "compositions", "customer.html")
open(out, "w", encoding="utf-8").write(html)
print(f"wrote {out}: {len(segs)} segments, {TOTAL} s of film")
