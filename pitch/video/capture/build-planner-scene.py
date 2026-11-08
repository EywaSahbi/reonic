"""Generates compositions/planner.html (scene 6, the planner's side) from the planner capture and its pointer log.

  python capture/build-planner-scene.py

Same machinery as scene 5 (build-customer-scene.py): the clip is cut into constant-speed segments, and the camera, the large pointer and the
step ticker are pure functions of film time derived from the same table. The planner window grows out of the placeholder that scene 5 ends on.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ev = json.load(open(os.path.join(HERE, "out", "planner.events.json"), encoding="utf-8"))

# (capture start, capture end, speed)
SEGMENTS = [
    (0.8, 4.6, 1.4),     # inbox, reo's summary is read
    (6.0, 10.4, 1.6),    # scroll to the satellite roof, the automatic placement around the obstacles
    (12.0, 15.9, 1.6),   # a module is dragged to a free spot
    (16.5, 21.6, 2.0),   # three modules are added
    (22.5, 28.5, 1.9),   # one removed, the price re-derives (banner)
    (28.5, 31.8, 1.3),   # the price breakdown, the changed rows
    (33.5, 41.8, 2.2),   # next steps: calendar event and CRM task approved
    (42.3, 45.2, 1.8),   # scroll to the note, Finalise in reach
    (45.2, 50.8, 4.5),   # the note is typed
    (50.8, 55.0, 1.3),   # Send, "Quote sent"
]

CAMERA = [
    (0.8, 1.0, (720, 450), 0.0),
    (2.4, 1.25, (840, 430), 0.9),     # reo's summary and the proposal table
    (9.0, 1.9, (850, 400), 1.0),      # the roof on the satellite photo
    (17.0, 1.45, (810, 500), 0.9),    # the roof, the count and the Add / Remove buttons
    (27.0, 1.2, (720, 520), 0.9),     # wider: the re-derive banner appears at the bottom
    (30.4, 1.25, (600, 520), 0.8),    # the price breakdown
    (36.0, 1.35, (1100, 500), 0.9),   # next steps
    (44.0, 1.3, (740, 560), 0.9),     # the note and Finalise
    (53.0, 1.2, (720, 600), 0.9),     # quote sent
]

STEP_MARKS = [("Summary", 0.33), ("Roof", 6.30), ("Edit", 12.19), ("Price", 27.93), ("Next steps", 33.71), ("Quote", 42.51)]
RESULTS_AT = 52.0

film0 = 0.0
segs = []
for c0, c1, r in SEGMENTS:
    dur = (c1 - c0) / r
    segs.append({"cap0": c0, "cap1": c1, "rate": r, "film0": round(film0, 4), "dur": round(dur, 4)})
    film0 += dur
TOTAL = round(film0, 3)

pointer, downs, last = [], [], None
for e in ev["events"]:
    if e["kind"] == "move":
        last = e
    elif e["kind"] == "arrive" and last:
        pointer.append([last["t"], e["t"], last["from"], last["to"]])
        last = None
    elif e["kind"] == "down":
        downs.append(e["t"])

mp4_rel = "assets/planner-capture.mp4"
clips = []
for i, s in enumerate(segs):
    hold = 1.8 if i == len(segs) - 1 else 0
    clips.append(
        f'            <video id="c6-v{i}" class="clip c6-vid" src="{mp4_rel}" muted playsinline data-start="{s["film0"]}" '
        f'data-duration="{round(s["dur"] + hold, 4)}" data-media-start="{s["cap0"]}" data-playback-rate="{s["rate"]}" data-track-index="{i}"></video>'
    )

# ---- the template is the customer scene's, re-coloured emerald and without the hand-off -------------------------------------
t = open(os.path.join(HERE, "customer.template.html"), encoding="utf-8").read()
t = t.replace("c5-", "c6-").replace('"customer"', '"planner"').replace("composition-id=\"customer\"", 'composition-id="planner"')
for a, b in [("#e8643c", "#0f9f7a"), ("#f6c9b2", "#bde5d8"), ("#fff3eb", "#eaf8f3"), ("#c9a999", "#7fb5a4"),
             ("rgba(232, 100, 60, 0.18)", "rgba(15, 159, 122, 0.18)"), ("rgba(232, 100, 60, 0.22)", "rgba(15, 159, 122, 0.22)")]:
    t = t.replace(a, b)
t = t.replace(">Homeowner<", ">Planner<")

# chips: six instead of four
t = re.sub(r'<div class="c6-chip" id="c6-chip0">.*?</div>\s*</div>', "".join(f'<div class="c6-chip" id="c6-chip{i}">{n}</div>' for i, (n, _) in enumerate(STEP_MARKS)) + "\n      </div>", t, count=1, flags=re.S)
t = t.replace("const chips = [0, 1, 2, 3].map(", f"const chips = [{', '.join(str(i) for i in range(len(STEP_MARKS)))}].map(")
t = t.replace("#c6-ticker { left: 900px; top: 20px; width: 780px;", "#c6-ticker { left: 760px; top: 20px; width: 920px;")
t = t.replace(".c6-chip { height: 40px; padding: 0 18px;", ".c6-chip { height: 40px; padding: 0 16px;")
t = t.replace("let active = cap < STEPS[0][1] ? -1 : 0;", "let active = cap < STEPS[0][1] ? -1 : 0;")

# drop the planner placeholder, the flying card and the hand-off (this scene is the planner's)
t = re.sub(r'\n    <div id="c6-plabel".*?<div id="c6-fly" class="abs">.*?</div>\n', "\n", t, flags=re.S)
t = re.sub(r"\n    /\* hand-off: the planner's side waits on the right \*/.*?(?=\n  </style>)", "", t, flags=re.S)
t = re.sub(r"\n    // hand-off: the plan leaves.*?\n\n    window\.__timelines", "\n\n    window.__timelines", t, flags=re.S)
# entrance: the planner window grows out of the placeholder scene 5 ended on (centre 1470,540, scale .6)
t = re.sub(r'    // entrance:.*?\n    tl\.fromTo\("#c6-win".*?\n', '    // entrance: the planner window grows out of the placeholder scene 5 ended on (centre 1470,540, scale 0.6)\n'
           '    tl.fromTo("#c6-win", { opacity: 1, x: 510, y: 0, scale: 0.6 }, { opacity: 1, x: 0, y: 0, scale: 1, duration: 0.85, ease: "power3.inOut" }, 0);\n', t, count=1, flags=re.S)

# the window folds into the centre as reo arrives (the ending starts at film 100.6 = local TOTAL + 1.4)
t = t.replace('    window.__timelines["planner"] = tl;',
              '    tl.to(["#c6-label", "#c6-ticker", "#c6-ptr"], { opacity: 0, duration: 0.25 }, TOTAL + 1.15);\n'
              '    tl.to("#c6-win", { scale: 0.08, x: 0, y: 0, opacity: 0, duration: 0.55, ease: "power3.in" }, TOTAL + 1.3);\n\n'
              '    window.__timelines["planner"] = tl;')
for marker, val in [("/*VIDEOS*/", "\n".join(clips)), ("/*SEGMENTS*/", json.dumps(segs)), ("/*CAMERA*/", json.dumps(CAMERA)), ("/*POINTER*/", json.dumps(pointer)),
                    ("/*DOWNS*/", json.dumps(downs)), ("/*STEPS*/", json.dumps(STEP_MARKS)), ("/*RESULTS_AT*/", str(RESULTS_AT)), ("/*TOTAL*/", str(TOTAL))]:
    t = t.replace(marker, val)

out = os.path.join(ROOT, "compositions", "planner.html")
open(out, "w", encoding="utf-8").write(t)
print(f"wrote {out}: {len(segs)} segments, {TOTAL} s of film (+1.2 s hold)")
