---
name: heavy-run
description: Check or tune how Claude sessions on this computer share CPU for tests, type checks and builds. Use when a run waits for tokens, when the user asks why tests are slow or who is running what, when the machine is overloaded by parallel sessions, or when setting up or tuning the heavy-run plugin (token count, memory floor, wait limit, shared service stack).
---

# heavy-run

The plugin's hook sends every heavy command through `heavy-run`. It tells you the wrapper's
full path when it denies a call; below it is written as `heavy-run`.

## How the sharing works

The computer has one pool of tokens, cores minus one by default. A whole suite, build, e2e run or
hook-running commit takes 3 tokens and gets 3 worker processes; a run narrowed to files or a name
filter takes 1 token and 1 worker; an explicit `-n N` or `--workers N` takes N tokens (up to the whole
pool). Playwright always counts as big. Big runs wait in arrival order, and the first one waiting
keeps each token as it frees up, so a stream of small runs cannot starve it; a small run still
starts when a token is left over beyond that. This is the same model
Kubernetes requests, the GNU make jobserver and Bazel's local resources use: admission counts
declared shares, not live CPU readings, because two sessions reading "6 cores idle" at the same
moment would both start and overload the machine. Live free memory is checked as a second gate.

## Running a long suite

Run a whole suite, e2e run or build with `run_in_background: true` and the timeout the hook's
message gives (7200000 ms, Claude Code's maximum); you are woken when it ends. A foreground call
is fine for a narrowed run. When the run ends or the call is stopped, everything it started is
stopped too, including a server you started inside it with `&`.

## When a run waits

1. Run `heavy-run --status` to see who holds the tokens and since when.
2. If you only need part of the suite, narrow it (a file path, `-t name`, `-k name`, `file::test`):
   it then takes 1 token and usually starts at once.
3. Otherwise wait. Do not split the suite into pieces to dodge the queue, and do not set
   `HEAVY_BYPASS=1` unless the user asks.
4. `heavy-run --reap` lists test workers whose parent died more than 30 minutes ago;
   `--reap --kill` stops them. Ask before killing.

## Settings (environment variables, in `settings.json` under `env`)

| Variable | Default | What it sets |
|---|---|---|
| `HEAVY_TOKENS` | cores minus 1 | Size of the shared pool |
| `HEAVY_BIG` | 3 | Tokens and workers for a whole suite or build |
| `HEAVY_MEM_MIN` | 15 | A new run waits while free memory is under this percent and someone else is running |
| `HEAVY_WAIT_MAX` | 2700 | Seconds a run waits before giving up with exit code 75 |
| `HEAVY_SERVICE_PATTERN` | unset | Regex for commands that use one shared service stack (fixed container names or ports); they run one at a time |
| `HEAVY_INNER_HOOK` | unset | Path of another Bash hook that should also check the commands inside `heavy-run` |
| `HEAVY_SIZE` | guessed | `small` or `big` for one run, when the guess is wrong |

Worker caps: vitest (`VITEST_MAX_WORKERS`, and the threads and forks caps for vitest 3 and older),
pytest-xdist with `-n auto`, cargo and Rust tests, make (unless `MAKEFLAGS` already has `-j`) and
gradle read variables; jest and Playwright read none, so `heavy-run -- jest ...` and
`heavy-run -- playwright ...` get `--maxWorkers=N` or `--workers=N` added to their arguments.

Also raise Claude Code's own Bash limit to its maximum, two hours, so a run can wait and then
finish: `"BASH_MAX_TIMEOUT_MS": "7200000"`. It caps foreground calls, and background calls cannot
run longer than two hours either. Sessions pick up `env` changes after a restart.
