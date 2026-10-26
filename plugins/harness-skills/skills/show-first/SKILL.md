---
name: show-first
description: Reference-first loop for a look the user judges by eye in their own apps: a new screen, sprite, icon, illustration, map style or store screenshots. Use before building it, or when the user says 먼저 보여줘, 레퍼런스, 구리다, or names an app to match. Not when a Figma or design spec already decides the look, not in team repos unless asked, not for a tweak to an existing look.
---

# Show first

The user is not a designer and judges this by eye, so the expensive mistake is building the wrong look. One wait up front replaces several rework rounds.

## Before building

1. **Find the references yourself.** Use the product the user named, plus its `DESIGN.md` when [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) lists it. A repo with no design contract yet (no root `DESIGN.md`, no design doc its CLAUDE.md points to) also gets 1–2 awesome-design-md products whose personality fits the subject, to seed the variants. Otherwise collect 2–3 strong references (store pages, app screenshots, field guides, galleries). Save them in the repo's `docs/design-reference/<surface>/` when that folder exists, else `.scratch/<feature>/refs/` (a working folder kept out of git), with a `README.md` line per image: product name, what to take, what not to take. Never ask the user to find references.
2. **Write the decision list**, at most 6 plain-Korean lines: what to copy from which reference, what to avoid, and the hard specs (grid, order, sizes, tokens from the repo's design source).
3. **Show one page** with the references, the decision list and 2–3 variants: an Artifact or a local HTML page for assets, `prototype`'s UI branch on the real route for screens. Ask one decision card, recommendation first (AskUserQuestion). This is the only wait before building.
   - The user is away (a loop, an overnight run): build the recommended variant, keep the others, and lead the report with the page.

## Building

4. Build the pick. Write the decision list to `docs/design-reference/<surface>/README.md`. In a repo with no design contract, also write the pick's tokens and their reasons as a root `DESIGN.md` in Google's format (any `awesome-design-md` file shows the shape), adapted to this product rather than copied, until `npx @google/design.md lint DESIGN.md` reports no errors.
5. Check mechanically before looking: overlap, cut-off text, contrast, touch targets of at least 44pt, tokens instead of literals, sprite grid and order. Turn each measurable rule into a test when the repo has a test runner.
   - When installed, run `token-compliance` from [design-system-ops](https://github.com/murphytrueman/design-system-ops) when the app has a token file, and [avoid-ai-design](https://github.com/funboy322/avoid-ai-design) (its scanner on web code; its catalog against the step 6 render). Fix every finding at the top two severities or write down why it stays.

## Looking

6. Render the real thing on the current tree with the `run` skill, at two sizes, in every state the change touches. Mobile (macOS): the current standard phone and the smallest one the app supports, picked from `xcrun simctl list devices available`. Web: 390×844 and 1440×900. Read every image you cite.
7. Build `.scratch/<feature>/compare.html`: a two-column grid (reference | ours), one row per state, and open it with `open`. Compare and fix for at most 2 rounds, then stop and show it.
   - Optional second opinion: a fresh-context subagent reads the page and reports only the differences that break a line of the decision list.
8. Before you call it done, show the user the compare page and the 1–3 differences that remain. The taste verdict is theirs.
