---
name: design-check
description: Design checklist distilled from repeated code-review findings. Use before writing code from a design or spec, before opening a PR, and when writing a design or architecture review. Covers dependency direction, where a shared guard lives, docs that must move with the code, tests that claim only real guarantees, races with deletes, and which layer owns a limit.
---

# Design check

Rules reviewers kept raising. Go through every one before the first line of code and again before the PR; fix what fails, or write down in the PR why it stays.

- **Dependencies point one way.** A base module that must import a module built on top of it means the design is upside down. Once you start adding type-only import stubs, lazy imports or protocol shells to dodge a cycle, stop and turn the direction around. A mixin that needs members of its host is better as a module function that takes the host as an argument.
- **A shared guard lives at one entry point.** Put the check once in the base class's public method (template method) instead of copying it into every subclass. If you need a meta-test that checks no copy was missed, the copying is the cost.
- **Design docs move with the code, in the same PR.** When a decision changes, change its line in the ADR or spec in that PR. Every place that repeats a number, list or name (overview, tables, QA notes, API descriptions) shows the same value.
- **Tests encode only the guarantees the code gives.** No docstring or assertion claims a guarantee that does not exist. If a race window remains, say it was narrowed, not closed. Prefer behaviour tests over meta-tests that inspect the code's shape.
- **Check races with delete and reindex first.** A compensating delete after the write can remove live data. Check before writing and skip the write when the target is gone; when the store has no conditional write, document the window.
- **Say which layer owns each limit and deadline.** For example, count and byte limits belong to the parser, time limits to the caller. Record the boundary in the ADR, and record "none" explicitly when there is no limit.
- **A design review sorts findings into savings, decisions and local trims.** Structural cleanups / items that need a decision (with an ADR) / local shortenings, each with a line count or cost in numbers, so the reader does not have to re-rank them.
