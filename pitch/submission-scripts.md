# reo — submission scripts (draft v2: two parties, one harness)

> Owner: `RaneemK-commits` (app). Two deliverables, one story: **2:00 product video** and **4:00 pitch**.
> The live five-minute judge demo stays in [demo-script.md](demo-script.md). Video and pitch reuse its exact inputs.
> Rules for every line: numbers come from the engine in that run; customer prices are "estimates"; honest validation including where we lose (hard rules 2–4).

## The framing (this is what changed in v2)

There are **two parties** and there is **friction** between them.

| | Homeowner (customer) | Installer (Sonnfeld) |
|---|---|---|
| Wants | An honest answer today, in plain words, without being sold to | Qualified leads, fewer repeated questions, offers out fast and right |
| Today's pain | Fills a form, then waits for a callback; no idea why a price is what it is | Planners spend hours on first drafts; every lead restarts from zero; context lost between web form, call and visit |
| What the gap costs | Drops out, or signs with whoever answers first | Slow offers, lost deals, expensive people doing repetitive work |

**Reonic already sits between the two** (the operating system installers run on). **reo takes it further:**
it is an **agentic companion dropped onto the installer's website** (built on a new agentic harness). It does not just pass information across the gap; it **does the installer's work**: talks to the customer, qualifies, designs, prices, compares with similar homes, drafts the offer, proposes the next steps. The human planner stays in control through an approval gate.

**Positioning line:** *Reonic connects installers and customers. reo does the work in between, under the installer's name and the planner's approval.*

What "agentic" means here, and what the repo can actually back up (use only these, no more):
- It **runs a job**, not a chat: reads the plan, compares with ~1,100 similar homes, builds three engine designs, checks the calendar, drafts the customer message, proposes actions (visit slots, quote).
- It has a **harness**: scoped tools only (engine calls), a grounding guard that checks every number against an engine result, run budgets, a visible step trace, and **actions that need a planner click** (`needs_approval`).
- It is **white-label**: the customer sees Sonnfeld's energy advisor, never "reo" or "Reonic"; the planner sees reo.
- It **degrades safely**: without an LLM key it runs a scripted planner with the same tools and approval flow.

Wording (decided): in the video and slides, simply say reo is *dropped onto the installer's website*; do not explain how. If asked, give the suggested implementation from the Q&A table, labelled as a suggestion. Never show a one-line embed snippet or say "install in minutes" (today it is a white-label widget in our React app plus an API). No named homeowner anywhere: say "a homeowner". Say the planner's work "takes hours", never a number.

Three phrases repeated in both scripts:
1. "Two sides, one gap."
2. "reo does the work in between."
3. "Numbers from the engine. Words from reo. Actions from the planner."

---

## A. Product video (2:00, hard cap)

**Visual device: the split.** The frame is divided in two: homeowner on the left, installer on the right, with a visible gap down the middle. The gap is the friction: a clock, a "waiting…" state, a message that goes nowhere. reo arrives *in* the gap, then the gap closes and becomes the product. In the demo, use **split screen** (customer window left, planner window right) so the viewer sees both parties move at once.

Style: Apple-style reveal. Warm paper, near-black ink, sunset gradient on one hero word per scene. One idea per scene, big type, slow voice. About 200 words of voice-over (≈130 wpm).

| # | Time | On screen | Voice-over | Notes |
|---|---|---|---|---|
| 1 | 0:00–0:12 | **Left half** (paper): "4,500 kWh" types in. Caption: "A homeowner. Wants solar. Knows one number." They type it into a form → "Thanks! We'll call you." Spinner. | "A homeowner wants solar. All they know is one number from their bill. They fill in a form, and then they wait." | No name. Detailed shots: [video-storyboard-1-4.md](video-storyboard-1-4.md). |
| 2 | 0:12–0:24 | **Right half** (slides in): installer inbox, a stack of "new lead" rows, a planner at a laptop, each lead restarting from blank. Caption: "The installer. Same questions. Every time." | "On the other side, an installer gets another lead that starts from zero. A planner will spend hours turning it into a design and a price." | Show "hours" with no number until confirmed (Open items). Gap in the middle: dashed line, a clock. |
| 3 | 0:24–0:32 | The gap widens. Text: "Reonic already connects the two." Then a beat. "reo goes further." | "Reonic already connects installers and their customers. We wanted to go further." | One calm line; no music hit yet. |
| 4 | 0:32–0:46 | **Reveal.** Reonic icon slides across and erases the wordmark, turns, becomes reo, waves, wordmark builds in: **reo**. Subtitle under it: "An agentic companion for installers." | "Meet reo. An agentic companion, dropped onto the installer's website, doing the work in between." | `ReoIntro withWordmark`, 4 s, hold 2 s, slow push-in. |
| 5 | 0:46–1:08 | **Split-screen demo, left = customer on Sonnfeld's site.** Taps: 4500 → address → EV *Planned* → heating *Gas*. Results: price range *estimate*, savings, 3D house building. Right panel still empty. Then **Send plan to Sonnfeld**. | "On Sonnfeld's website, reo talks to the homeowner in the installer's name. Four taps, and she has a design, a price range, and a reason for every number." | Speed-ramp the typing. Callout "Tap any number to see why." Customer sees "Sonnfeld", never "reo". |
| 6 | 1:08–1:26 | **Right = planner view lights up as the plan arrives.** **reo appears in the planner view wearing the vest (first use).** Offer-pack timeline streams: reads the plan → compares ~1,100 similar homes → 3 engine designs → drafts message → ✓ numbers verified. Variant cards. Then **Approve** on the proposed visit slot (the approval click is the beat). | "Meanwhile reo is already working for the planner. It compares similar homes, builds three designs, drafts the offer, and checks every number against the engine. Then it asks. Nothing happens until the planner says yes." | Real run ~15 s, show ~8 s. Hold the green "numbers verified" tick 1 s, and the **approval click** 1 s. |
| 7 | 1:26–1:36 | Planner drags two modules off the roof in the design studio; banner "re-derived". Then **Finalise and send quote**. Left window: *Confirmed quote* in the planner's own words. | "The planner stays in charge: change anything, and every number re-derives. The estimate becomes a confirmed quote, in the installer's own words." | The gap in the middle of the screen **closes** here. |
| 8 | 1:36–1:52 | Night panel. "Tested on 235 homes it never saw." Chart `vs_baseline_test.png`. **49 % vs 42 %** PV within ±20 %. Honest line: "Batteries: still hard." Then "49 of 52 'no solar' misses already had solar. So reo asks." | "Agents are only useful if you can trust them. So reo only uses a deterministic engine, and we tested it on 235 real homes it had never seen. It beats the baseline on solar sizing, we show where it doesn't, and the biggest miss taught it the question to ask." | Battery figure: **data's frozen M3 number only** (39 % vs 42 % now, disputed with engine's 45.6 %). Do not publish a battery line until data republishes. |
| 9 | 1:52–2:00 | Both halves merge. reo lockup, blink. "Two sides, one gap. reo does the work in between." URL. | "reo. For every installer, a colleague that never sleeps." | End on the blink. Final URL only after the last deploy. Check the tagline is not read as "replaces the planner". |

### Video production notes
- **Can I build the intro? Yes.** `ReoIntro` is a pure SVG on one clock, frame-exact. Plan: **HyperFrames** (HTML to MP4) for scenes 1–4, 8, 9 (the split, the gap, the reveal, the proof) with `ReoIntro` dropped in as an SVG scene; plain 1080p captures for the demo scenes 5–7 as clips, composed into a split screen in the same composition.
- Capture the demo with **two windows, clean state** (`Start over`, local live stack, voice off), 1920×1080, 60 fps.
- Voice-over: human preferred. A reo/ElevenLabs voice is a nice touch for scenes 4–7 only.
- Captions burned in. Export 1080p H.264; keep a no-music version.

---

## B. Pitch (4:00, slides)

Four equal judging criteria (technical depth, user fit, business impact, execution/demo) get about a minute each. The new framing makes **user fit** and **business impact** concrete because there are two named users.

Slides are HTML with animation; for the PDF every slide must read in its **final frame**, and the validation slide must work as a static table.

| # | Time | Slide | What is on it | Say |
|---|---|---|---|---|
| 1 | 0:00–0:15 | **Hook** | Split slide: left "4,500 kWh" (homeowner), right a stack of leads (installer), a gap between. | "Two people, one solar system. A homeowner who knows one number, and an installer who needs forty answers." *(replace "forty" with a confirmed figure or drop it)* |
| 2 | 0:15–0:45 | **Friction** | Two columns with the table above, condensed: Homeowner waits / Installer repeats. Middle: "Reonic connects them." | "Between the two there's friction: the customer waits and drops out, and the planner spends hours on first drafts and starts every lead from zero. Reonic already connects installers and customers. We asked what happens if the connection does the work." |
| 3 | 0:45–1:05 | **Reveal** | `ReoIntro` plays to the lockup. Tagline: "An agentic companion for installers." | "This is reo, an agentic companion dropped onto the installer's website, white-labelled, doing the work between customer and planner." |
| 4 | 1:05–2:10 | **Demo** (65 s) | Live app, split screen: customer left, planner right. | See demo cut below. Keep narrating both parties: "she…", "the planner…". |
| 5 | 2:10–2:45 | **The harness** | Diagram: Customer ↔ reo (words) → Engine (numbers) ← Data (evidence) → Planner. Four chips: *scoped tools*, *grounding check on every number*, *run budgets and trace*, *planner approval gate*. Small note: "No key? Scripted mode, same flow." | "Agentic AI in a business that sells roofs needs guardrails. reo can only call the engine's tools. A code guard checks every number in its text against an engine result. Every run is traceable, and anything with an effect waits for a planner click. The agent proposes; the planner decides." |
| 6 | 2:45–3:20 | **Evaluation** | Table from `reality_check_test.md` plus `vs_baseline_test.png`. Callout: "49 of 52 'no solar' misses = existing solar". | "235 homes the engine never saw, trained on the rest. We beat the baseline on solar size and don't on batteries. The biggest miss was missing data, so reo now asks about existing solar." |
| 7 | 3:20–3:45 | **Value for both sides** | Two columns. Installer: first draft in minutes, ready offer, planner on exceptions, leads qualified before the call. Homeowner: answer today, reasons for every number, nothing sent unconfirmed. Metric placeholders flagged. | "For the installer: time per offer and win rate, with the planner doing the judgement, not the legwork. For the homeowner: an answer today and a reason for every number." |
| 8 | 3:45–4:00 | **Close** | reo lockup, URL, repo, team. "Two sides, one gap. reo does the work in between." | "Reonic connects installers and customers. reo does the work in between. Thank you." |

### Pitch demo cut (slide 4, 65 s) — two parties, both narrated

| Time | Do | Say (one sentence) |
|---|---|---|
| 0:00 | Customer window: Sonnfeld site, **Plan my home**, type **4500** | "A homeowner has one number." |
| 0:10 | Address **Musterstraße 12, 80331 München**; EV **Planned**; heating **Gas** | "An address, a car, a heating system." |
| 0:22 | Results: price range (*estimate*), payback, 3D house; tap one number | "A design, a price range, a reason for every number, from the engine." |
| 0:36 | **Send plan to Sonnfeld**, name **Anna Demo** | "She hands over to Sonnfeld." |
| 0:42 | Planner window: offer pack streams, ✓ numbers verified, variants; point at proposed visit slot | "The planner doesn't start from zero: reo already did the comparison, three designs, a draft." |
| 0:52 | Click **Approve**; design studio: remove two modules, Apply, point at re-derive banner | "reo proposes, the planner approves. Edits re-derive." |
| 0:59 | **Finalise and send quote**, flash the customer window: *Confirmed quote* | "Estimate becomes confirmed quote. Gap closed." |

Live or clip? Run live only with the recorded fallback queued on the next slide. If the offer pack is still *preparing* after 15 s, click **Prepare again** (scripted pack, under 1 s). Full fallback table in [demo-script.md](demo-script.md).

### Q&A cheat sheet

| Question | Answer |
|---|---|
| Is this just a chatbot? | No. The chat is the customer-facing half. The agent's job is the planner's work: comparison, three designs, draft offer, proposed actions, with a trace. |
| Does it replace the planner? | No. It does the first draft; effectful actions need a planner click, and the planner can edit any number. |
| Is the LLM making up numbers? | No. Tools only, plus a code guard that rejects any number not in an engine result; the retry is visible in "Ask reo why". |
| How does an installer adopt it? | **Our suggested implementation** (not built yet, say so): (1) the installer adds a small embed to their site, a script tag that mounts the white-label advisor with their brand and persona; (2) it talks to a hosted reo backend configured with the installer's price list and calendar; (3) finished plans land in the planner view, connected to the Reonic system, where the planner approves. Today's demo is the same pieces as a widget in our app plus an API. |
| Why is battery sizing weak? | Existing equipment and installer preferences are not in the data; we say so on the slide. |
| What is real vs mocked? | Engine, pricing, harness: real. Address lookup: demo addresses mocked. Prices: public German market ranges, estimates until the installer confirms. |
| Data privacy? | The dataset never leaves the team; an LLM call sees only the one home in the conversation. |
| What next? | More installer price lists, existing-equipment capture from the bill reader, real roof outlines, a packaged embed. |

---

## C. Reusing components

| Component | Video | Slides |
|---|---|---|
| The split (customer / gap / installer) | scenes 1–3, 9 | slides 1, 2, 8 |
| `ReoIntro withWordmark` | scene 4, 9 | slide 3, 8 |
| Customer flow capture | scene 5 | slide 4 |
| Offer pack + approval + design studio | scenes 6–7 | slide 4 |
| Harness diagram | (scene 6 hint) | slide 5 |
| Validation chart + counters | scene 8 | slide 6 |

Build each once as an HTML component with a `time` prop (like `ReoIntro`): the video renders it frame by frame, the deck plays it on click, and the PDF gets a static final state.

## Open items before recording

- [x] **Packaged embed:** not needed for the video; "dropped onto the installer's website" is all we claim, and the suggested implementation is a Q&A answer only.
- [ ] **Hours per offer / leads / win-rate numbers:** ask a Reonic expert on site (board `DECISION`); until confirmed no number on screen.
- [ ] **How Reonic's system fits:** one confirmed sentence from the team on how reo connects to the Reonic system today, so slide 2 doesn't overclaim.
- [ ] **Battery validation number:** use data's frozen M3 value; do not publish the battery line until it is republished.
- [ ] Actual kWp and price range from a clean run (engine version at freeze).
- [ ] Final demo URL and repo link. Vercel frontend is **not** redeployed since the Living advisor work (needs `cd app && npx --yes vercel --prod`).
- [ ] "Sonnfeld" name clearance.
- [ ] Voice-over: human or reo's ElevenLabs voice.
- [ ] Re-record after the code freeze (M3, Sun 12:00).
