# What prospect-sim Predicts — and What It Cannot

**A first-principles guide to reading simulation output correctly.**

---

## The Mental Model

prospect-sim is not a crystal ball. It is a **controlled experiment environment** for human cognitive behavior under a specific stimulus — a cold email.

Each run does one thing: places a synthetic decision-maker (built from your ICP profile) in front of your email copy, and records what they do. Open it. Read past the opening. Reply. Archive. Forward. Do nothing.

The predictions are only as reliable as two things:
1. **How accurately the synthetic persona matches your real ICP** — which depends on the quality of your seed document.
2. **How well the behavioral model captures real inbox decision-making** — which is calibrated against real-world send data over time.

Everything that follows flows from understanding this.

---

## The Prediction Hierarchy

Not all outputs carry equal weight. Listed from most to least reliable:

### 1. Failure Point Diagnosis — Most Reliable
**What it tells you:** Where your copy loses the reader — subject line, opening line, body, or CTA.

This is the most reliable output because it doesn't depend on calibrated absolute rates. It depends only on *which cognitive hurdle the email fails to clear*. A persona who never opens the email failed at the subject line. A persona who opens but doesn't read to completion failed at the opening hook. A persona who reads fully but doesn't reply failed at the body or CTA.

The mechanism of disengagement is well-modeled. The number of agents who disengage is less reliable than the point at which they disengage.

**Use this to:** Diagnose exactly which part of your copy needs surgery, not just "this variant underperformed."

---

### 2. Relative Variant Ranking — Reliable
**What it tells you:** Variant A outperforms Variant B, with a confidence magnitude (3x, 1.5x, tied).

The ranking is more reliable than the absolute numbers. If Variant B (timeline hook) consistently gets more reply intents than Variant A (problem hook) across 30+ synthetic personas, that directional signal is meaningful — even if the absolute simulated reply rates don't match real-world rates.

The magnitude matters too. A 3x difference between variants is a strong signal. A 1.1x difference is noise.

**Use this to:** Pick the winner before sending to real leads. Discard the obvious losers early.

---

### 3. Persona Segment Sensitivity — Reliable with Good Seed Docs
**What it tells you:** Variant A resonates with risk-averse budget-holders; Variant B resonates with early-adopter Heads of People.

When personas are built from rich, specific ICP seed documents, their `decision_style`, `cold_email_skepticism`, and `pain_signal_sensitivity` fields create meaningfully different agents. The same email copy will behave differently across them — and that divergence is real signal.

**Use this to:** Segment your outreach. Don't send the same script to a conservative 300-person company HR Director and an agile 50-person startup Head of People.

---

### 4. Absolute Rate Estimates — Least Reliable
**What it tells you:** "Variant A has a 12% simulated reply rate."

This number is **not calibrated against real-world send data** until you run Phase 6 validation (simulate a known campaign, compare to actual results, measure the delta). Until that calibration exists, absolute numbers are directionally useful at best and misleading at worst.

**Use this only for:** Internal ranking (12% vs 4% → strong signal for the winner). Never report these numbers externally as predictions of real reply rates.

---

## What You Can Test

### Copy-level tests (vary the email, same ICP)

| Variable | What the simulation captures |
|---|---|
| Subject line | `open_email` vs `do_nothing` — the 3-second subject test |
| Hook type | `read_to_completion` after opening — problem / timeline / numbers / authority |
| Email length | `body` dropout point — where attention breaks |
| CTA friction | `cta` dropout point — "book a call" vs "reply with 3 slots" vs "watch Loom" |
| Social proof presence | Affects `decision_style=social_proof` personas more than `decision_style=roi_driven` |
| Personalization level | Generic vs company-specific references — captured in persona's engagement triggers |
| Pain point framing | Which pain you lead with — varies by `pain_signal_sensitivity` weights on each persona |

### ICP segment tests (same copy, vary the audience)

| Variable | How to run it |
|---|---|
| Job title (HR Director vs Head of People vs VP People) | Different seed docs describing each persona type |
| Company size (50 vs 150 vs 500 employees) | Seed doc describes company size context |
| Industry vertical | Include industry-specific context in seed doc |
| Pain awareness level | Seed doc describes whether the prospect is actively problem-aware or not |
| Specific prospect simulation | Feed a real prospect's LinkedIn + company page as seed doc |

### Structural tests (vary the format, same message)

| Variable | What it tests |
|---|---|
| Short (3 sentences) vs long (8+ sentences) | Attention and cognitive load |
| Plain text vs formatted (bullets, bold) | Format-triggered skepticism in certain personas |
| First-person narrative vs data-led opening | Persona `decision_style` response |
| Question opening vs statement opening | Curiosity vs authority triggers |

---

## What You Cannot Predict

### 1. Absolute reply rates
The simulated 12% is not a prediction of real-world 12%. It is a relative signal. Calibration against real send data is required before treating these numbers as forecasts.

### 2. Multi-touch sequence dynamics
The system models a single email. It does not model what happens when email 1 gets no reply and email 2 follows up with "bumping this to the top of your inbox." Sequence fatigue, follow-up timing, and persistence effects are out of scope for v1.

### 3. Organizational politics
The simulation models an individual decision-maker. It does not model that the real prospect's boss just signed a contract with a competitor, that they're in a hiring freeze, or that their company was acquired last week. No seed document captures real-time organizational context.

### 4. Accumulated brand familiarity
If a prospect has seen your brand at a conference, follows you on LinkedIn, or was referred by a trusted colleague — that context fundamentally changes reception. The simulation starts from a cold, uncontextualized state.

### 5. Time-of-day and day-of-week effects
The `inbox_habit` field (morning_scanner, batch_processor, responsive) is modeled in the persona, but simulation rounds are not mapped to real clock time. Send-time optimization is not something the current system predicts.

### 6. Forward chain effects
When a persona forwards your email to a colleague, the simulation logs it as a strong positive signal but does not model what the colleague does with it. The chain stops at the first forward.

### 7. Reply content quality
The simulation records whether a persona replies — not what they say. It doesn't predict the quality of the conversation that follows.

---

## How to Read the Results

**The question to ask first:** "Where did each variant lose agents, and why?"

Not: "Which variant has the highest simulated reply rate?"

A variant that loses 80% of agents at the subject line and has a 12% reply rate among those who open is a fundamentally different problem than a variant that passes the subject test but loses agents at the CTA. Same reply rate, different surgery needed.

**The ranked output tells you:**
1. The winner — highest combined open + reply intent signal
2. The loser's failure mode — subject, opening, body, or CTA
3. Which persona types responded differently — and why

**The failure heatmap tells you:**
- If all personas fail at the subject line: the subject is the problem, the body is irrelevant
- If personas fail at the opening: the hook is the problem
- If personas fail at the CTA: the ask is too high-friction for this ICP
- If failure is distributed across points: the email has multiple problems; fix the earliest one first

---

## Calibration — How to Know if Your Simulation is Working

prospect-sim generates real value when its relative rankings match real-world results. The way to establish this:

**Step 1:** Run a simulation on a copy variant whose real-world performance you already know. If you've sent 300 emails with a problem-hook script and 300 with a timeline-hook script and know the real reply rates — run both through the simulation.

**Step 2:** Check if the simulation correctly identifies the winner. If yes: your ICP seed document is well-calibrated. If no: your seed document doesn't accurately reflect your real ICP — iterate on it.

**Step 3:** Once calibrated, treat future simulations as reliable signal for that ICP segment. The absolute numbers remain fictional; the rankings become trustworthy.

For Skillia specifically: benchmark data shows timeline hook (~10%) outperforms problem hook (~4.4%) on HR Director personas at Spanish SMEs. A calibrated simulation should reproduce this ranking. If it does, the system is ready for predicting new copy variants.

---

## The Compound Value

The simulation's value compounds with use. Each calibration run teaches you more about:
- How accurately your seed documents model your real ICP
- Which persona fields drive the most behavioral variance (is it `cold_email_skepticism` or `decision_style` that matters most?)
- Which copy variables move the needle for your specific market

Over 10–20 simulation runs, you build a reliable intuition about what the system can and cannot predict for your use case. That intuition is itself a competitive advantage — most teams are still burning real leads to test hypotheses you can validate in 10 minutes.

---

## Summary

| Output | Reliability | Use for |
|---|---|---|
| Failure point diagnosis | High | Surgical copy fixes |
| Relative variant ranking | High | Picking the winner before sending |
| Persona segment sensitivity | Medium-High (with rich seed docs) | Segmenting outreach |
| Absolute rate estimates | Low (until calibrated) | Internal ranking only |
| Real-world reply rate forecast | None (until calibrated) | Not yet |

**The north star:** prospect-sim tells you which variant to send and where the loser breaks. It does not tell you how many replies you'll get. That distinction is the difference between using it correctly and being surprised when the numbers don't match.
