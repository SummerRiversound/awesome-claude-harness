---
name: ready-review
description: Review gate before a draft PR is flipped to ready. Use when the user asks to mark a PR ready, asks for the pre-ready review, or the PR flow reaches that step. Three read-only reviews run in parallel (defects, standards, spec), then one fix agent commits every finding it cannot refute with evidence, and the fix commits are reviewed again before the PR goes ready; only open questions come back to the user.
---

# Ready review

A draft PR is flipped to ready only through this gate. The human reviewer sees a finished result, not a list of findings to act on. The review agents carry the coding standards; the implementation context does not need to.

## 1. Preconditions (main session)

- Working tree clean, every change committed on the PR branch.
- Fresh base: `git fetch`. When HEAD does not contain `origin/$base` (or, for a stacked PR, the default branch the base should already hold), rebase first; decisions merged in between are part of the review. Review the lower PR of a stack before the upper one, then rebase the upper.
- Fixed point: `base=$(gh pr view --json baseRefName -q .baseRefName)`, then `git merge-base origin/$base HEAD`. The diff under review is `git diff <merge-base>...HEAD`.
- Spec source, first found wins: the linked issue (`gh pr view --json closingIssuesReferences`), a spec file the repo keeps for this feature, the PR body's Summary.
- Standards sources: every agent instruction file the repo has (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `CONTRIBUTING.md`, `docs/design-system/` when present), plus the repo's decision record when it has one (`docs/DECISIONS.md` and the ADRs under `docs/ADR/` whose topic the diff touches). A change that contradicts an accepted ADR is a finding.
- Layer 1 first: run the repo's own check scripts (lint, type-check, unit tests). A failure is implementation work, not review: fix, commit, then start.
- If project memory holds a subagent-operations note for this repo (git-guard quirks, scratchpad collisions, test flags), paste it into every agent prompt below.

## 2. Review (parallel, read-only)

Spawn all of these in one turn. Reviewers do not edit or commit; each writes its full report to `<session scratchpad>/review-pr<N>-<axis>.md` (`defects`, `standards`, `spec`) and also returns it. Put that absolute path in every reviewer prompt, the code-review skill's two sub-agents included, so compaction cannot lose a report.

**Small diff**: Markdown, config or manifests only under about 100 changed lines; tests only (no product code) under about 100; or product code under about 150. Run Defects and Spec only, Spec as one `Agent` with `model: opus` that also checks the diff against the repo's documented standards and the conventions of the file it lands in, and apply step 3 in the main session instead of a fix agent. The outcome rules stay the same.

- **Defects**: `Agent` with `model: opus`, adversarial. Try to break the change: wrong output for concrete inputs, races, missing error paths, regressions in callers, security. Every finding carries a failure scenario (inputs/state → wrong result) plus file and line. Also report test gaps: tautological tests (the expected value restates the code or a constant), structure-coupled tests, tests whose mocks make them unable to fail, tests whose fake DOM (happy-dom, jsdom) asserts a layout or scroll value no real browser would produce — those emulators never clamp or lay out, so the value is whatever the test set. When the change branches on a value another service sends (a message string, an error code, a status), check that the **deployed** version of that service, not only an unmerged branch, produces a value the tests cover — a branch written against the unmerged wording never runs in production. Run a mutation check on each guard, limit or branch the diff adds: remove the line, run the nearest tests, and report it when they still pass. Search for the same cause outside the diff (sibling call sites, the other code path that computes the same value) and report every copy the change left. Then look past the edited path: name the other features that read a value or stored shape the diff changes (paired repo included), the other entry points to the same action, and the permission checks, filters or masks the existing path enforces, and report each one the change breaks, skips or leaves untested. Read the PR body claim by claim: a sentence the diff, a test or a measurement does not back ("also blocks X", "all N paths") is a finding. A claim that rests on another service or module (its ordering, limits, permission gate, who reads a stored value) is checked in that service's code on its fetched default branch, and the reviewer prompt lists the open PRs the change depends on. Finally, when the body carries a `Door: one-way|two-way` line, check it: a destructive migration, data deletion, external send, API-contract, auth, or shared URL/storage-format change labelled `two-way` is a finding. Confirm in a real browser only when a finding may be P0/P1; for P2/P3 a code read and a unit test are enough.

  Human reviewers find what a read-only pass misses by running things. The Defects agent does the same; a path it only read counts as unreviewed:
  - **Run what the diff adds.** Every script, CLI path or workflow step, with real inputs and the network stubbed: non-ASCII paths, partial success, one failing item before a good one.
  - **Plant what a removed check caught.** For every assertion, test or fixture the diff removes or loosens, name the defect it used to catch, plant it, and report it when no remaining test fails.
  - **Differential check for translations.** When the diff translates between two representations it claims are equivalent (a query and its rewrite, an old and a new reader, a port of a rule from another language), run both on generated edge inputs (shadowed names, aliases, nesting, null against empty, wrapped queries) and report every input whose results differ.
  - **Values already stored.** For each new rejection, limit or changed meaning, state what happens to values already stored and to clients that resend them unchanged, and whether they must be counted before deploy.
  - **Pinned references.** Every commit SHA, submodule, git dependency or image tag the diff pins must be reachable from its source repo's default branch; a SHA that exists only on an open PR is blocking.
  - **The real flow of the paired service.** Trace each shape the diff sends to or reads from another service through that service's fetched default branch and its open PRs. A step that works only because a test seeds state the real flow never creates is a finding; state what breaks if this PR deploys before or after its pair.
  - **Modes PR CI does not run.** For every renamed or newly required fixture, export or env var, search every importer, including integration-only, nightly and sample suites, and report those that break.
  - **Docs against docs.** Check each edited doc against the docs it cites as well as the code (requirements against test cases, a report against the changes it summarises, a decision record against its index), and report any sentence a reader would act on wrongly.
  - **Severity is the cost of merging as-is**: data loss, an out-of-order deploy, a removed guard, unbounded work, a decision doc left contradicted, not only wrong output.
- **Standards + Spec**: call the Skill tool with `mattpocock-skills:code-review` (from [mattpocock/skills](https://github.com/mattpocock/skills)), passing the fixed point, the spec source, and the standards sources. It spawns its own two sub-agents, run with `model: opus`: Standards (documented rules plus the Fowler smell baseline) and Spec (missing, extra, or wrong requirements). Keep its two reports separate; do not rerank across axes. A formatting finding is reported only after the repo's formatter or linter fails on that line; what the pre-commit formatter produced is not a finding.

## 3. Fix (one agent, after all reviews return; the main session for a small diff)

`Agent` with `model: opus` (fixing is implementation, not review), in the main checkout, after every reviewer has returned (never concurrently with them). Prompt = the three report file paths (read each in full before acting), the spec source, the fixed point, and any decision the user made in this conversation that bears on a finding, each quoting the user's words. The main session's own plans go in a separate list and are not refutation evidence.

Every finding gets exactly one outcome:

- **Fix and commit**: a defect, a documented-standard breach, or a spec gap. Apply the smallest fix, rerun the repo checks, commit (conventional, English, imperative; one commit per logical fix). Never widen scope beyond the finding.
- **Refute with evidence**: a test that proves the behaviour, a spec line, a documented repo standard that overrides a baseline smell, or a user decision. "Judgement call" alone is not evidence.
- **Open**: needs a decision the user has not made (two valid designs, spec ambiguity, one-way-door risk). State the question and a recommendation.

It reports one table, finding → outcome (commit sha, the evidence, or the open question), and nothing else.

## 4. Review the fixes (main session)

Skip this step when step 3 committed nothing. Otherwise the fix commits are code no reviewer has seen.

- **One more pass**: a fresh Defects agent over `git diff <sha before the fixes>..HEAD`, with the whole diff as context. Its prompt carries the user's decisions and nothing from step 2: no report, no finding list, no fix table. A reviewer that has seen the first round confirms it.
- **It reports blocking findings only**: wrong behaviour with a failure scenario, a breach of a documented standard, or a spec gap that a fix introduced or left. The reviewer sets the class; step 3 may refute a finding with evidence but never reclassifies one to get to zero.
- **A blocking finding** goes back through step 3 and its fix is reviewed the same way, three passes at most. When the third still has one, stop: the PR stays draft and the user gets what keeps coming back.
- **Not converging**: when a pass finds as many as the one before, the same place again, or a defect inside a fix, stop fixing and name the reason first.
  - The same cause shows up in new places: fix the cause once instead of each finding.
  - Each fix breaks something else: the change is too tangled. Add the missing tests first, or split the PR.
  - Reviewers contradict each other, or the spec reads two ways: it is a decision, not a fix.
  - Findings are scattered over unrelated areas: the PR is too large. Split it.

  A root-cause fix inside the PR's scope you make and report. A redesign, a split or a spec decision is an open item for the user, with what recurs and a recommendation.
- **After ready too**: commits pushed in answer to a human review get the same pass before the reviewer is asked to look again. A fix made under review is as unreviewed as one made before it.
- **Rebase before, tidy after**: bring in the base (step 1) before the pass you expect to be clean; a rebase after it voids it. Once the pass is clean, history may be tidied: fold each fixup into the commit it fixes and keep the commits that mean something on their own. `git diff <clean sha> HEAD` must print nothing, and then no new pass is needed.

## 5. Close (main session)

- Each report opens with the HEAD sha it reviewed. If the tree changed after the last clean pass (anything but a history tidy whose diff is empty), review the new commits before going on.
- Push. Re-check the whole PR body against what was actually committed and the current base: `Door:` / `Blast radius:`, evidence and test counts, stacking notes.
- Open items: present them to the user with the recommendation. The PR stays draft until they decide.
- Review-bot threads (Codex, Copilot): each one has a reply or is resolved before the PR goes ready; a human reviewer who has to repeat a bot finding has been handed unfinished work.
- Nothing open: `gh pr ready`. Then call the Skill tool with `session-retro`.
