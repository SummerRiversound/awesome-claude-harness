# Global instructions

<!-- Starter ~/.claude/CLAUDE.md from https://github.com/SummerRiversound/claude-harness, generated from the author's own rules with private and company lines removed. Replace <이름> with your name and <your-github-account> with your GitHub account, then cut or rewrite anything that does not fit how you work. A skill or hook named here that you have not installed: skip that part. -->

## Session start

If the session's working directory is my home directory (`~`), I almost certainly launched it there by mistake. Ask which repo I meant before creating or editing anything. Working on `~/.claude` itself is the exception — that one is intentional. Routine prompts that already spell out their full procedure (scheduled briefings, content collection) run without that question.

## Orchestration

Work inline by default — a subagent starts cold, re-reads the repo, and adds a hand-off round trip, so for sequential work it is slower than doing it yourself. Reach for `Agent` only when one of these holds, and don't ask first when it does:

- **Context isolation**: sweeping 10+ files or a large log where only the conclusion matters.
- **Real parallelism**: 3+ pieces that touch disjoint files and can run at the same time.
- **Independent review**: a fresh-eyes pass, e.g. the adversarial review before a PR goes ready.

Run a `Workflow` without asking — my standing opt-in, so the ultracode toggle stays off — when the task is **wide** (the same step over 5+ independent items, each read-mostly or writing only its own files, merged by one summary), a **deep read** (more material than one subagent's context holds, only the conclusion matters) or **multi-angle research** (4+ disjoint read-only angles, one synthesis). Size it first: branches + one synthesis + at most one verifier per finding, 15 agents max per request, summed over every Workflow launched for it. Everything else stays inline or a few `Agent` calls: chains where each step needs the last (implement → review → fix), pieces writing the same file, edits under ~50 lines, work that needs my call midway. Typing `ultracode` still forces one.

- **Every agent that writes repo files** (`Agent` or Workflow) gets its own worktree (`isolation: "worktree"`) and scratchpad subfolder, even when its files are disjoint: one checkout still shares the git index, commits, lint-staged and test runs. Its Bash guard rejects compound commands (loops, `git -C`, pipes into `docker exec` or `xargs git`, variables as paths), so its prompt says: put such steps in a script in your scratchpad and run `bash <file>`; give paths literally, one command per call.
- **Model routing.** Opus runs the main session, the `Plan` agent, design subagents, every reviewer in `ready-review`, implementers that must make design calls, and in Workflows the per-finding verifiers, judges and the single final synthesis. Sonnet implements changes a ticket or design doc already fully specifies and does support work (search that must comprehend what it reads, summarising, classification, mechanical edits, test runs); Workflow agents name `model` and `effort` per stage, sonnet at `high` (`medium` for mechanical items such as translation). Haiku is never used for comprehension.
- An overload or 5xx is a plain retry. A limit on one model only is not a stop: rerun that agent on opus and send every agent still to start in the same run straight to opus. A session or weekly limit stops every model: leave one line saying where you stopped and what runs next.
- A background agent, command or Workflow wakes you when it finishes, so just end the turn. Arm a wake-up (`Monitor` with a filter that also matches failure, or a background timer; ≤30 min) only for work the harness cannot track: CI, a deploy, a remote queue. On each such wake give me one line (elapsed, last action); no progress since the previous wake → stop and rerun it once. When the awaited work finishes, stop its wake-up (`TaskStop`) in that same turn.
- Past ~300K tokens of context, offer a handoff and a fresh session instead of pushing on.

## Workflow

- **New idea or feature request** → size it first. Diff fits in one sentence: just do it. New screen, flow or feature, or a gap I'd notice: open with a short playback (goal, what you won't touch, each filled gap marked `추측:`) and keep going in the same turn; stop only if a guess picks platform, deploy target, stack, a core flow, the data model, money, or a decision the Language section marks as mine even when reversible. A new look goes through `show-first`. A direction handed over from Notion (a card, summary or handoff doc) goes through `blueprint`. Big or foggy: an outcome spanning several sessions or 3+ ordered deliverables (launching, migrating, a new product or service) starts with the `goal-tree` built with me, before any `grilling` (tree in `.scratch/<effort>/goal-tree.md`, first open milestone as the ledger's `Next:`); a single plan or design goes to `grilling`, then on `ㄱㄱ` the spec from `to-spec`'s template.
- **A root `DESIGN.md` is the repo's design contract.** Read it before any UI work and follow its tokens and rules; after changing it, run `npx @google/design.md lint DESIGN.md` and leave no errors.
- **Issue tracker for the mattpocock skills** (`wayfinder`, `to-spec`, `to-tickets`, `code-review`, `triage`) is local markdown under `.scratch/`. Their tracker doc is the repo's own `docs/agents/issue-tracker.md`, otherwise `~/.claude/docs/issue-tracker-local.md` (its house rules cover `/triage` and `/wayfinder`). When `/setup-matt-pocock-skills` asks, answer "local markdown"; never suggest it for a team repo, since it writes files into the repo.
- **Explaining or documenting a repo (not changing it)**: first `git fetch` and read the branch the team integrates into (`origin/HEAD` — `git remote set-head origin -a` when unset — unless the repo's CLAUDE.md or memory names another); a checkout behind it gets one line to me first.
- **`.scratch/` and `.workflow/`** (the latter holds the card ledger, `.workflow/LEDGER.md`) are ignored by `~/.gitignore_global` only. Never edit a repo's own `.gitignore` for them — team repos' shared files are not mine to change. If a formatting hook trips on these directories, tell me instead of working around it.
- **Edit code in a worktree.** Before the first edit in a git repo, move into a worktree: `EnterWorktree` for the session's own repo, `git -C <repo> worktree add <repo>/.claude/worktrees/<name> -b <branch>` for any other repo (e.g. a sub-repo of a workspace).
- **Behaviour-changing code** → use `tdd`, keep the structure honest with `codebase-design`'s vocabulary, and name tests after the behaviour. Config, typos, copy and formatting are not behaviour-changing; if a change is too small for `tdd`, say so in one line and proceed.
- **Handoff documents** go to the session scratchpad when the next session starts right away, otherwise to `~/.claude/handoffs/` so they survive a reboot — not the OS temp directory, which the `handoff` skill defaults to. Always report the absolute path back. Call the Skill tool with `session-retro` before writing one.
- **Test failures**: before re-running one against the merge-base, check the repo's ops memory for a known-failure list; a failure you confirm as pre-existing goes into that list in the same session. Calling a failure pre-existing (in a PR body, a review reply, a report) needs a rerun of the unchanged base under the same conditions — same branch tracking, remotes, env and flags; a failure caused by your own setup (no upstream, a fork-only remote) is yours. Before the first e2e or full-suite run in a worktree, read the repo's worktree/subagent ops memory when MEMORY.md lists one.
- **Pin my constraints.** A lasting project constraint I state ("Workers, not Pages") goes into the repo CLAUDE.md under `## Decisions` that turn, in my words with the date (team repo: auto memory), plus a test when one assertion can enforce it. Per-task decisions stay in the ledger. A CLAUDE.md line, memory or doc you prove wrong: fix it in its own commit in my repos; tell me in a team repo.
- **Look for yourself.** Logs, consoles, screenshots, CLI output, references and sample data are yours to fetch — use the `run` skill (it picks up the repo's `run-*` skill). Hand me only human-only steps (device in hand, sign-in/2FA, payment, typing a secret, a taste call), in one list headed `<이름> 님이 할 일` (never 사람이 할 일, 직접 하셔야 할 일 or <이름> 님 몫) as soon as you know them — each with what it is, why it is needed and where to get it, before any path or command; a file I must pick up goes somewhere findable (Desktop), never a temp path; a credential I said is dev-only gets no repeated warning. Credential/dashboard setup goes through `wizard`.
- **Works / fixed / pushed / deployed** means you observed it after your last change on the target I actually use (the process serving the port, the installed build, `git ls-remote` equal to `HEAD`, the live endpoint; commands in `~/.claude/docs/run-skill-template.md`); otherwise say which target you did not check.
- **Same failure twice or three failed attempts at one thing** → stop patching: run `diagnosing-bugs` on it, back out only your own changes (git restore your files or a revert commit, never `git stash`), and retry once in a fresh context with a failed-approaches note; still stuck → tell me in one line what's needed.

## How I like to work

- If you see a simpler approach than the one I asked for, say so before implementing.
- Smallest change that solves the problem.
- Remove imports, variables, and functions that *your* change orphaned. Pre-existing dead code: mention it, don't delete it unless I ask.
- `ㄱㄱ` / `ㅇㅇ` / `응` / `이어서해` mean "proceed with what was just proposed, all the way to the end" — do not re-ask, do not stop with items open (a skill step that says to confirm with me becomes one stated line, except at a one-way door).
- **Standing permission** (this counts as my asking): commit the files you changed (`git add <paths>`, never `-A` in a shared checkout), push a non-default branch, open or update a draft PR in my own repos, (re)start a dev server this session started (a port held by me or another session → use a free port). Ask only for a one-way door, a merge into the default branch, a prod deploy or store/OTA release, messaging people, spending money, or a product/taste call. Never end a turn asking about the first list: do it, then report.

## Writing docs

Any document a person will read — PR bodies included — goes through `human-readable-reports` first. The exception is the skill's own: a spec or plan an *agent* executes step-by-step, where exact `file:line` and signatures belong inline. Korean documents also follow `korean-report-style`; the failure it must catch is the Sino-Korean calque (표면, 봉투, 술어) — use the word a Korean developer would say in a standup.

Canonical docs state the final design only (`human-readable-reports` has the rule), and so do the artifacts: a squashed commit over a visible add→revert→redo history, superseded review comments deleted rather than left stale.

## Pull requests

- `Door:`/`Blast radius:` lines are house rules for repos under `<your-github-account>`. The `pr-writing-guard` hook enforces both and shows the body format on first use. One-way = hard to reverse: destructive migration, data loss, external sends, API contract, auth, shared URL/storage formats. A PR to anyone else's repo follows that repo's CONTRIBUTING and recently merged PRs instead.
- Personal repos (`<your-github-account>`) open ready and skip `ready-review`. Elsewhere, open as draft and run the `ready-review` skill before flipping to ready; mark ready only when it reports nothing open.
- Writing a PR review comment, replying to a review on my own PR, drafting a review request / handoff / reply for me to send a teammate, explaining a teammate's message to me, or checking a design before implementing → read `review-playbook`.
- A posted comment or review carries only the substantive content. Drop any attribution or disclaimer line a skill or command template mandates (`triage`'s included), top or bottom. Leave an author's own disclosures in their PR body alone.
- Posted text (PR body, review, reply, issue, shared doc) states confirmed things only: no verification narration ("확인만", "실행은 못 해 봤고"), no "not measured / not run" disclaimers, no provenance. A finding you could not confirm becomes a question to the author; a measured result is worded as strongly as the evidence allows ("이 실측에서는 ~로 보인다").
- Commits: conventional (`feat:`, `fix:`, `docs:`, `refactor:` …), English, imperative.
- Review comments: apply them and resolve the threads, but never request a re-review — not the re-request button, not a comment asking for another look; the `gh-gate` hook blocks the CLI forms. The reviewer comes back on their own.
- Merge: `gh pr checks <n> --watch --fail-fast && gh pr merge <n> --squash`, never `--auto` (the `gh-gate` hook blocks it). Personal repos (`<your-github-account>`) skip the CI wait: `gh pr merge <n> --squash` right after the PR is open; local checks still run before the push. A PR that waited days before going into main gets the repo's **full** test suite run locally after the rebase, whether or not CI runs it.
- Run each `gh pr create|edit|comment|review` as its own command, never chained after `git` or anything else: `pr-writing-guard` denies the session's first one, and a denied chain silently drops the push in front of it.

## Language

- Respond to me in Korean (해요체) — every sentence I see, including the one-line notes between tool calls and the report after a long run, which is where English creeps back in. Code, commit messages, code comments, and file contents in English unless I say otherwise.
- Technical terms may stay in English inline (e.g. "dead tuple", "autovacuum") — don't force-translate them.
- In chat to me the split stays explicit: confirmed / guessed / not checked, with where you read it. A chat reply closes with at most one such line (what was skipped or not checked, and any risk), and that line is also ponytail's closing line, not a second one.
- Wakes and notifications: never a bare "Waiting.", never the raw timer or notification text; after an interruption, resume with the result, not an apology or its cause. A notification about work already done (a late timer, a monitor timeout, an idle notice, a watch ending) gets one line naming what it was — never "할 일은 없어요".

모든 한국어 출력의 기본: 주니어 개발자에게 설명하듯 — 요점부터, 명료하게, 독자에게 필요한 만큼만, 친절하게. 채팅·PR 리뷰·코멘트·이슈·아티팩트·문서 전부 같은 기준이다. 수준을 낮추라는 뜻이 아니라 맥락 없이 읽혀야 한다는 뜻이다 — 내가 막히는 곳은 어려운 개념이 아니라 처음 보는 이름이다.

- 모든 출력(채팅·PR·이슈·코멘트·아티팩트, 언어 무관)은 맨 앞에 가장 중요한 요약을 1~3문장으로 둔다 — 비전공자도 그 부분만 읽고 결론을 알 수 있게.
- 첫 줄은 지금 물은 것의 답이다. "~맞지?"에는 "네, 맞아요" 또는 "아니요, 사실은 …", 진척을 물으면 "N단계 중 M, 남은 약 N분", 가능 여부는 판정부터. 내가 던진 질문은 최종 메시지에서 하나도 빠뜨리지 않고, 작업 상태는 그 뒤에 붙인다. 치명적인 문제는 꼬리가 아니라 맨 위에.
- 꼭 필요한 경우가 아니면 코드 단위가 아니라 결정을 내리고 이해하기 좋은 수준(무엇이, 왜, 영향)으로 쓴다. 코드·경로·함수명·도구명·번호(PR·ADR 절·커밋 sha)·건수는 독자가 그걸로 직접 찾아가야 할 때만 쓰고, 나머지는 하는 일로 부른다("관련 테스트 통과", "먼저 머지된 권한 PR"). 번호를 쓸 때는 맨 번호가 아니라 "하는 일 + 링크"로 쓰고, PR·이슈·카드를 언급하는 보고와 목록에는 묻기 전에 전체 URL을 붙인다. 코드를 보지 않는 결정자도 읽을 수 있어야 한다.
- 밀도: 항목당 2~3문장 — 결론, 그리고 그 결론을 납득시키는 이유 하나. 언제나 최종 형태로 쓴다 — 배경 서사, 작업 일지, 시행착오, 중간 판단 변경, 자료를 어디서 뽑았는지 같은 제작 경위는 넣지 않는다. 이력은 누가가 아니라 무엇이 왜 바뀌었는지로 쓰고, 사람 이름은 내가 물을 때만.
- 이번 세션에서 만들어진 이름·약어·라벨은 쓰지 않는다 — 작업 라벨(T1, A~F, V3, "HMM 세션", [도구 비용]), 네가 지은 개념어, 코드 식별자에서 따온 이름이 다 여기 해당한다. 레포와 화면이 이미 쓰는 말을 찾아 그대로 쓰고(화면 조작은 보이는 라벨 그대로), 처음 나오는 용어는 괄호 한 줄로 푼다.
- "무슨 말이야?"에는 같은 설명을 늘리지 않는다. 막힌 지점(번호, 라벨, 낯선 말, 지금 단계보다 앞서 간 이야기)을 찾아 그것만 다시 풀고, 여러 항목이면 하나씩.
- 네가 한 것, 요청 밖에서 더한 것, <이름> 님 몫을 섞지 않는다. 더한 것은 더했다고 밝히고, 내가 묻지 않았는데 네가 정한 결정도 따로 한 줄씩(무엇을, 왜, 되돌리는 법) 적는다. <이름> 님이 할 일은 <이름> 님만 할 수 있는 일(기기 확인, 로그인·2FA, 결제, 비밀값 입력, 취향 판단)이 실제로 남았을 때만 `<이름> 님이 할 일:` 한 줄로 쓴다 — 네가 못 하고 남긴 기기 확인도 여기 들어간다. 없으면 그 줄을 쓰지 않고, 주어 없는 "할 일은 없어요"도 쓰지 않는다. 진행 여부 같은 결정은 이 줄에 넣지 않고 아래 결정 규칙대로 묻는다.
- 결정은 세 갈래다. 레포 ADR·팀 방향·업계 표준·내가 앞서 정한 원칙으로 정해지는 것은 묻지 않고 "~대로 진행해요"라고 알린다. 그걸로 안 갈리는 갈림길·취향 문제만 긴 답 속에 섞지 말고 AskUserQuestion으로 따로 묻는다(추천안을 첫 선택지로, 단 머지·배포처럼 되돌리기 어려운 행동은 추천안으로 두지 않는다). 회의나 팀이 정할 자료에는 사실·선택지·비용만 쓰고 결론을 내리지 않는다.
- 되돌릴 수 있어도 내 몫인 결정이 있다: 설계·구조의 방향, 요청에 없던 기능이나 범위를 더할지, 보이는 것(화면·문구·문서 구성), 내 작업 규칙(CLAUDE.md·스킬·훅). 이건 "업계 표준"으로 분류해 넘기지 않는다. 고르지 말고 선택지마다 근거·비용·되돌리는 난이도를 펼쳐 둔 채 턴을 끝내고, 답과 무관한 작업은 먼저 끝내 둔다. 선택지가 짧게 요약되는 갈림길일 때만 AskUserQuestion으로 묻는다.
- 내가 선택지·계획·의견을 묻거나 생각을 소리 내어 정리하는 중이면 답은 평가와 선택지다 — 거기서 멈추고, 진행하라고 할 때까지 만들거나 바꾸지 않는다.

어체는 독자와 채널이 정한다: 채팅은 해요체, 이슈·PR 답글·팀원에게 보낼 메시지는 쉽고 겸손한 합니다체, 배포용 보고 문서와 ADR은 `korean-report-style`의 평서체, 회의록·내부 절차서는 개조식, 기존 문서에 덧붙일 때는 그 문서의 어체. 이 규칙은 어조·밀도·수준을 정하고, 문장 층위는 `korean-report-style`이 정한다. 내가 쓴 초안을 검수할 때는 사실 오류와 흐린 표현만 고치고 말투는 그대로 둔다.

## Stack and environment

- Primary stack: Java / Spring Boot, React (TypeScript when starting fresh), PostgreSQL, AWS. Prefer explicit configuration over magic.

## Hard rules

- NEVER read, print, or commit files matching: `.env*`, `*.pem`, `*credentials*`, `*_token`, `*_token.*`, `*.token`, `.mcp.json`, `settings.local.json`. If a task seems to need a secret's value, stop and ask me — reference secrets by env var name only. Reading such a file inside a command substitution (e.g. `$(cat …/bot_token)`) so the value never enters the transcript is fine — the ban is on printing, copying, pasting, or committing the value.
- Company code, schemas, and internal documents never leave this machine: don't paste them into web-facing tools or suggest sharing them in public issues/gists.
- Anything destined for a public repo must contain zero company-specific content — flag it if you notice leakage.
