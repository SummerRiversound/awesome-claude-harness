# claude-harness

**One place to install a working Claude Code setup.** These are the skills and rules I use every day, with everything private or company-specific taken out: a review gate before a PR goes ready, a retrospective that improves the setup over time, references before building a new look, goal trees for big jobs, and reports a person can read on the first pass.

![license](https://img.shields.io/badge/license-MIT-555) ![works with](https://img.shields.io/badge/works%20with-Claude%20Code-2f8f5b)

## What's inside

| Plugin | What it does |
|---|---|
| `harness-skills` | **ready-review**: three reviews in parallel (defects, standards, spec) before a draft PR goes ready, then one agent fixes what it cannot refute. **session-retro**: a one-turn retrospective that proposes changes to your setup, not your code. **show-first**: gathers references and shows you options before building a screen, icon or other look you judge by eye. **design-check**: a checklist distilled from repeated review findings (dependency direction, docs moving with code, tests that claim only real guarantees), run before coding and before a PR. |
| [`goal-tree`](https://github.com/SummerRiversound/goal-tree) | Before a big job, builds the goal tree with you: top goal, sub-goals, ordered milestones you can check. |
| [`human-readable-reports`](https://github.com/SummerRiversound/human-readable-reports) | Rules that make agent-written reports, PR bodies and docs readable on the first pass. |
| [`review-inbox`](https://github.com/SummerRiversound/review-inbox) | A drawer with your GitHub work: PRs waiting for your review, your PRs and your issues. |

All skills are model-invoked: Claude reaches for them when the situation fits, so you rarely type them.

## Install

```
/plugin marketplace add https://github.com/SummerRiversound/claude-harness.git
/plugin install harness-skills@claude-harness
/plugin install goal-tree@claude-harness
/plugin install human-readable-reports@claude-harness
/plugin install review-inbox@claude-harness
```

Install only the ones you want. `/plugin update` keeps them current.

## Works best with

These are other people's plugins the skills above lean on. Install them from their own repos:

| Plugin | Why |
|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills) | `ready-review` uses its `code-review`; `show-first` uses its `prototype`; also `tdd`, `grilling`, `diagnosing-bugs` |
| [ponytail](https://github.com/DietrichGebert/ponytail) | Smallest-change discipline and short replies |
| [interfaces](https://github.com/jakubkrehel/skills) | UI reviews (accessibility, layout, typography, color) |
| [fluent-korean](https://github.com/snflkd/fluent-korean) | Natural Korean output |
| [korean-report-skills](https://github.com/JangHyun-bin/korean-report-skills) | Sentence rules for Korean reports |
| [superpowers](https://github.com/obra/superpowers) | `receiving-code-review`: verify review feedback before applying it |

## Starter rules

[`templates/CLAUDE.md`](./templates/CLAUDE.md) is my global `~/.claude/CLAUDE.md` with the private lines removed. It is regenerated from my own copy, so it stays current.

1. Copy it to `~/.claude/CLAUDE.md` (or merge it into yours).
2. Replace `<이름>` with your name and `<your-github-account>` with your GitHub account.
3. Cut anything that does not fit how you work. The language section assumes you want answers in Korean; rewrite it if not. Skills or hooks it names that you have not installed can be skipped.

## License

MIT, see [`LICENSE`](./LICENSE). The linked third-party plugins keep their own licenses.
