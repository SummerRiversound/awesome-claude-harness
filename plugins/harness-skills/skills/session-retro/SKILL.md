---
name: session-retro
description: One-turn retrospective on the current session, run on its own right after a PR is flipped to ready and right before a handoff document is written. Proposes changes to the agent's environment (navigation pointers, automated checks, reviewer standards, steering-file bloat, tool economy, information access), never to the code, and appends them to ~/.claude/retro/ so compaction cannot lose them. Also on request ("레트로", "retro this session").
---

# Session retro

A model-invoked twin of the user-only `retro` skill in [mattpocock/skills](https://github.com/mattpocock/skills): the same checklist, run at fixed points so nobody has to remember it. It looks back at THIS session as held in context (no transcript reading) and suggests changes to the environment the agent works in, not to the code. The user decides what to adopt; nothing here is applied.

## When it runs

- Right after `gh pr ready` (ready-review step 4).
- Right before a handoff document is written.
- On request.

Once per trigger per session. A trivial session (no code change, no review finding, no friction) gets one line in chat and no file.

## What to look for, worst first

- **Navigation**: the agent spent a long time finding a file, a command, or a convention → a pointer line for CLAUDE.md/AGENTS.md, or a doc to link.
- **Automated checks**: a mistake the agent made, or a reviewer caught, that lint, types, a test, or a filesystem check could have caught → name the check. Read the repo's own check scripts and CI first: a check that exists but is unwired or silently broken is the finding, not a new one. A repo with no guardrail at all is a finding in itself.
- **Reviewer standards**: a mistake the reviewers missed. Classify first: mechanical (a fixed pattern, a banned API, an import shape, a file location) → a deterministic check, never a prose rule; a judgement call (cross-file consistency, "matches the surrounding style") → one line for the reviewer's standards source.
- **Steering-file bloat**: an instruction in CLAUDE.md/AGENTS.md that changed nothing this session, or that belongs in a reviewer standard or a check instead.
- **Tool economy**: an expensive or repeated tool call: large outputs read into context, a subagent spawned for a one-fact lookup, a hook that cost seconds per call.
- **Information access**: something the agent needed and could not see (a log, a service, where a credential lives) → how to open it.

Keep the two-stage model in mind: implementation carries the most context pressure (explore, write, debug); review carries the least (a diff, no exploration). Standards belong on the review side; CLAUDE.md/AGENTS.md hold pointers.

## Output

1. In chat, in Korean: at most five findings, severity first, one line each: `[분류] 무슨 일이 있었나 → 제안 (하네스 / 레포 PR / 팀 결정)`. Nothing to report → one line, no file.
2. Append the same list under a `## <YYYY-MM-DD> <one-line session gist>` heading to `~/.claude/retro/<repo>.md`, newest section first; `<repo>` is the git repo's directory name, `harness` for work in ~/.claude. Create the directory and file as needed. The file is the backlog the user reads later; never mark anything there as adopted on your own.
