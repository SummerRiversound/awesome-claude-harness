# heavy-run

**Run many Claude Code sessions on one computer without freezing it.** Each session that starts a
test suite, type check or build normally grabs every core it can. With five sessions doing that at
once, the laptop stalls, tests time out and the sessions retry, which makes it worse. This plugin
makes those commands share the cores instead.

## What it does

1. A hook checks every Bash call. Tests, type checks, builds, e2e runs, `pre-commit run`, and
   `git commit` or `git push` in a repo whose own hooks run, are sent back with the command to
   use instead: the same command wrapped in `heavy-run`.
2. `heavy-run` takes tokens from one pool shared by every session (cores minus one). A whole
   suite or build takes 3, a run narrowed to a file or test name takes 1. When the pool is empty
   the run waits; whole suites and builds go in arrival order, and small runs cannot cut in front
   of one that is waiting.
3. The run gets as many worker processes as tokens: it sets the caps vitest, pytest-xdist,
   cargo, make and gradle read, adds `--maxWorkers` or `--workers` for jest and Playwright, and
   sets `HEAVY_WORKERS` for anything else.
4. When the run ends, its whole process group is stopped, so no test workers are left behind.
   That includes anything started inside it with `&`. If the wrapper itself is killed, the
   command keeps its tokens until it exits, and so does anything it left running in the background.
5. If free memory is low and other runs are going, a new run waits for memory too.

Counting shares instead of measuring idle CPU is deliberate. Two sessions that both see six idle
cores start at the same moment and overload the machine; counted shares cannot double-book.
Kubernetes, the GNU make jobserver and Bazel admit work the same way.

## Install

```
/plugin marketplace add https://github.com/SummerRiversound/awesome-claude-harness.git
/plugin install heavy-run@awesome-claude-harness
```

Then add this to `env` in `~/.claude/settings.json` and restart Claude Code. It raises Claude
Code's Bash limit to its maximum, two hours, so a run can wait for tokens and still finish. The
hook asks Claude to run whole suites in the background, which has the same two-hour ceiling.

```json
"BASH_MAX_TIMEOUT_MS": "7200000"
```

Needs Python 3 and macOS or Linux.

## Use

You rarely type anything: Claude reruns the command through the wrapper when the hook asks.

```
heavy-run -- npx vitest run            one command, argv form
heavy-run 'npm test && npm run lint'   one shell string
heavy-run --status                     who holds the tokens, load, free memory
heavy-run --status --json              the same as one JSON object for programs (a parallel runner reads tokens_free to decide how many units to start)
heavy-run --reap [--kill]              orphaned test workers older than 30 minutes
```

Settings and tuning are in [`skills/heavy-run/SKILL.md`](./skills/heavy-run/SKILL.md).
To skip the check for one command, put `HEAVY_BYPASS=1` in front of it.

## Limits

- Programs started outside the wrapper (Docker containers, editors, a video call) are not
  counted. The memory gate is the backstop for those.
- Worker caps work for tools that read them. A tool that ignores them can use more than its share.
- Dev servers and watch mode (`--watch`, `test:watch`) never finish, so they are let through, not
  wrapped and not counted.
- The hook reads the command line, plus any shell script it runs (`bash <file>`, `sh -e <file>`,
  `./<file>` with a shell shebang): up to three levels deep, the first 256 KB of each. A sourced file
  (`source`, `.`) is not read, since those are mostly rc and env files.
  `npm run lint` is caught because the script name says so, but a bare `eslint .` is not, a custom
  script name such as `npm run ci` is not either, and neither is a Python or Node script that starts
  tests itself.
- Commands passed through `xargs`, `watch` or `find -exec` are not caught.

## Tests

```
python3 -m unittest discover -s plugins/heavy-run/tests
```
