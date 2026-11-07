# reo — conversation flow

> Owner: `RaneemK-commits` (app). The reo backend follows this. Starter draft: rewrite freely.

## Customer side

1. **Hello.** reo introduces itself in one line and asks for the one fact it needs: annual electricity use (or, if unknown, how many people live in the home).
2. **First design, immediately.** reo shows the engine's first design with a price range and says what would make it more precise.
3. **Refine, highest impact first.** reo asks for the engine's top `missing_inputs`, roughly in this order: heating type → EV now or planned → roof size (or address for a lookup) → electricity price → budget. The customer can skip any question; reo works with assumptions and says so.
4. **Questions welcome.** "Why a battery?", "Why does it cost that much?", "What if we skip the heat pump?" are answered from the engine's reasons and what-ifs.
5. **Handoff.** When the range is tight enough (or the customer asks), reo offers: "Shall I send this plan to <installer>? They will check it and send you a final quote." Ask for name and email.
6. **Final quote.** Once the installer finalises, the customer sees the confirmed plan and price.

## Installer side

- Opens with a one-paragraph summary: the home, what the customer cares about, the proposed system and price, open questions, and flags where the plan differs from similar real projects.
- The installer can edit anything; reo explains what changed as a result.
- The installer can ask reo "why …?" about any decision.
- Finalise sends the quote to the customer.
