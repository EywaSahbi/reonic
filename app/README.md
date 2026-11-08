# app/ — the web UI (customer site, advisor, planner workspace)

> Back to the [project README](../README.md). Owner: `RaneemK-commits`. React + Vite + TypeScript on `:5173`; talks to the reo backend only.

Two views behind one hash route:

| URL | View |
|---|---|
| `/` | **Customer site**: the white-label installer website ("Sonnfeld") with the step form / advisor reo, the live plan card (3D house, price range marked as estimate, savings, payback), heat-pump comparison, handoff |
| `/#/installer` | **Planner workspace**: inbox of handed-over plans → plan detail with the roof editor, design studio, price breakdown, reasons, flags, offer pack, "Ask reo why", approve/reject proposed actions, finalise and send the quote |

## Highlights

- **Living stage**: the advisor explains any number you tap, with voice (ElevenLabs) in and out.
- **Roof editor** ([`src/RoofEditor.tsx`](src/RoofEditor.tsx)): the satellite photo and traced outline with the PV modules already placed; drag, add, rotate, remove, undo, reset. Only the module count is a number; it re-derives the design.
- **Design studio** ([`src/scene/DesignStudio.tsx`](src/scene/DesignStudio.tsx)): 3D build mode for modules and hardware sizes; folds into its title bar when real map data exists.
- **Offer pack and traces** ([`src/OfferPack.tsx`](src/OfferPack.tsx)): the offer agent's variants, checklist, draft message and a replayable step trace.
- **Offline mock** ([`src/mock.ts`](src/mock.ts)): the UI runs without a backend when `VITE_API_URL` is not set.

## Files

| Path | Role |
|---|---|
| [`src/main.tsx`](src/main.tsx) | hash router (customer vs planner) |
| [`src/App.tsx`](src/App.tsx), [`Widget.tsx`](src/Widget.tsx), [`PlanCard.tsx`](src/PlanCard.tsx) | customer site, step form/advisor, plan card |
| [`src/Installer.tsx`](src/Installer.tsx) | planner workspace |
| [`src/api.ts`](src/api.ts), [`types.ts`](src/types.ts) | the only place that calls reo; types mirror `reo/CONTRACT.md` |
| [`src/scene/`](src/scene/), [`src/live/`](src/live/) | 3D house and design studio, living stage |
| [`scripts/`](scripts/) | deployment checks and the Windows backend/tunnel helpers |

## Read next

[DEPLOYMENT.md](DEPLOYMENT.md) (Vercel + tunnel, access codes, limits) · [docs-3d.md](docs-3d.md) · [docs-installer-ideas.md](docs-installer-ideas.md) · [STATUS.md](STATUS.md).

## Run

```bash
cd app
npm install
VITE_API_URL=http://localhost:8001 npm run dev    # without VITE_API_URL: in-browser mock
npm run build                                     # must pass before every push
```
