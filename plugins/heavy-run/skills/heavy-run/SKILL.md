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
filter takes 1 token and 1 worker. A run waits until its tokens are free. This is the same model
Kubernetes requests, the GNU make jobserver and Bazel's local resources use: admission counts
declared shares, not live CPU readings, because two sessions reading "6 cores idle" at the same
moment would both start and overload the machine. Live free memory is checked as a second gate.

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

Also raise Claude Code's own Bash limit so a run can wait and then finish in the foreground:
`"BASH_MAX_TIMEOUT_MS": "3600000"`. Sessions pick up `env` changes after a restart.
